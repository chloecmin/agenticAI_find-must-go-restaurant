import os
import math
import csv
from pathlib import Path
from typing import List, Dict, Any
from elasticsearch import Elasticsearch

# ElasticSearch는 실제 환경에서만 필요하므로, 테스트 환경에서는 없어도 동작하도록 처리
try:
    from elasticsearch import Elasticsearch  # type: ignore
except ImportError:
    Elasticsearch = None

# -----------------------------
# 1) 기존 ES 기반 검색 (실서비스 용)
# -----------------------------
def get_es_client() -> Elasticsearch:
    """
    ElasticSearch 클라이언트 생성.
    ES_HOST 환경변수에서 호스트 주소를 읽는다.
    """
    host = os.getenv("ES_HOST", "http://localhost:9200")
    return Elasticsearch(hosts=[host])


def search_es(
    query: str,
    index: str | None = None,
    size: int = 5,
) -> List[Dict[str, Any]]:
    """
    ElasticSearch에서 간단한 multi_match 검색을 수행하는 유틸 함수.
    LangChain tool 래핑은 llm_tools.py에서 한다.
    """
    es = get_es_client()
    index = index or os.getenv("ES_INDEX", "restaurant_docs")

    body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "content", "body", "text"],
                "type": "best_fields",
            }
        },
        "size": size,
    }

    res = es.search(index=index, body=body)
    hits = res.get("hits", {}).get("hits", [])
    docs: List[Dict[str, Any]] = []
    for h in hits:
        docs.append(
            {
                "id": h.get("_id"),
                "score": h.get("_score"),
                "source": h.get("_source", {}),
            }
        )
    return docs


# -----------------------------
# 2) CSV + BM25 기반 테스트용 검색
# -----------------------------
def _tokenize(text: str) -> List[str]:
    """
    매우 단순한 토크나이저.
    - 영문은 소문자 변환
    - 공백 기준 split
    - 한글은 그대로 둠 (공백 기준 토큰)
    테스트용이므로 복잡한 형태소 분석은 하지 않는다.
    """
    if not text:
        return []
    return text.lower().replace(",", " ").replace("/", " ").split()


def _build_bm25_index(rows: List[Dict[str, str]], fields: List[str]):
    """
    주어진 rows(각 row는 CSV 한 줄)와 사용할 필드 리스트를 받아
    BM25 계산에 필요한 통계값을 만든다.
    반환값:
    - docs_tokens: 각 문서별 토큰 리스트
    - doc_lens: 각 문서 길이
    - avgdl: 평균 문서 길이
    - df: 토큰별 document frequency
    """
    docs_tokens: List[List[str]] = []
    doc_lens: List[int] = []
    df: Dict[str, int] = {}

    for row in rows:
        # 여러 필드를 이어붙여 하나의 문서 텍스트로 사용
        parts = []
        for f in fields:
            val = row.get(f)
            if val:
                parts.append(str(val))
        doc_text = " ".join(parts)
        tokens = _tokenize(doc_text)
        docs_tokens.append(tokens)
        doc_lens.append(len(tokens))

        seen = set()
        for t in tokens:
            if t not in seen:
                df[t] = df.get(t, 0) + 1
                seen.add(t)

    avgdl = sum(doc_lens) / len(doc_lens) if doc_lens else 0.0
    return docs_tokens, doc_lens, avgdl, df


def _bm25_score(
    query_tokens: List[str],
    docs_tokens: List[List[str]],
    doc_lens: List[int],
    avgdl: float,
    df: Dict[str, int],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[float]:
    """
    각 문서에 대해 BM25 점수를 계산해 리스트로 반환.
    """
    N = len(docs_tokens)
    scores = [0.0 for _ in range(N)]

    # query term 빈도는 따로 고려하지 않고, unique query term 기준으로만 합산 (테스트용이므로 단순화)
    for q in set(query_tokens):
        if q not in df:
            continue
        n_q = df[q]
        idf = math.log((N - n_q + 0.5) / (n_q + 0.5) + 1)

        # 각 문서에서 q의 term frequency 계산
        for i, tokens in enumerate(docs_tokens):
            tf = tokens.count(q)
            if tf == 0:
                continue
            dl = doc_lens[i] if doc_lens[i] > 0 else 1
            denom = tf + k1 * (1 - b + b * dl / (avgdl if avgdl > 0 else 1))
            score = idf * (tf * (k1 + 1) / denom)
            scores[i] += score

    return scores


def search_es_csv_bm25(
    query: str,
    csv_path: str | Path | None = None,
    size: int = 5,
) -> List[Dict[str, Any]]:
    """
    테스트용: ES 대신 CSV를 불러와 BM25로 가장 적합한 식당을 찾는다.

    - CSV는 restaurants_mock.csv 형식(예시):
      restaurant_id,name,area,category,keywords,latitude,longitude,address,rating,user_ratings_total,review_snippet

    - 검색에 사용할 필드:
      name, area, category, keywords, address, review_snippet

    반환 형식은 ES 버전과 최대한 유사하게 맞춘다:
    [
      {
        "id": <restaurant_id>,
        "score": <bm25_score>,
        "source": <row 전체 dict>
      },
      ...
    ]
    """
    csv_path = Path(csv_path or os.getenv("RESTAURANTS_CSV_PATH", "data/restaurants_mock.csv"))

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {csv_path}")

    # CSV 로드
    rows: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return []

    # BM25 인덱스 구축
    fields = ["name", "area", "category", "keywords", "address", "review_snippet"]
    docs_tokens, doc_lens, avgdl, df = _build_bm25_index(rows, fields)

    # 쿼리 토큰화
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # BM25 점수 계산
    scores = _bm25_score(query_tokens, docs_tokens, doc_lens, avgdl, df)

    # 점수 기준 정렬
    ranked = sorted(
        enumerate(rows),
        key=lambda x: scores[x[0]],
        reverse=True,
    )

    results: List[Dict[str, Any]] = []
    for i, (idx, row) in enumerate(ranked[:size]):
        score = scores[idx]
        # ES 호환 구조로 반환
        rid = row.get("restaurant_id") or row.get("id") or str(idx)
        results.append(
            {
                "id": rid,
                "score": float(score),
                "source": row,
            }
        )

    return results
