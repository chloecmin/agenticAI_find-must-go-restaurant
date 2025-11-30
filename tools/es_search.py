import os
import math
import csv
from pathlib import Path
from typing import List, Dict, Any
import requests

# 기존 ElasticSearch import
try:
    from elasticsearch import Elasticsearch
except ImportError:
    Elasticsearch = None

###########################################
# 1) 음식 종류 추출 및 매핑 (한식, 일식, 중식 등)
###########################################

def extract_cuisine_type(query: str) -> tuple[str | None, str]:
    """
    쿼리에서 음식 종류를 추출하고 영어 키워드로 매핑
    
    Args:
        query: 검색 쿼리
        
    Returns:
        (cuisine_keyword, translated_query) 튜플
        - cuisine_keyword: cuisines 필드 필터링용 키워드 (예: "Korean", "Japanese", "Chinese")
        - translated_query: 번역된 쿼리
    """
    import logging
    logger = logging.getLogger(__name__)
    
    query_lower = query.lower()
    
    # 국가별 음식 매핑 (한글 → 영어 키워드)
    cuisine_mapping = {
        # 한식
        "한식": "Korean",
        "한국": "Korean",
        "한국음식": "Korean",
        "korean": "Korean",
        
        # 일식
        "일식": "Japanese",
        "일본": "Japanese",
        "일본음식": "Japanese",
        "japanese": "Japanese",
        
        # 중식
        "중식": "Chinese",
        "중국": "Chinese",
        "중국음식": "Chinese",
        "chinese": "Chinese",
        
        # 양식 (Western)
        "양식": "Western",
        "서양": "Western",
        "western": "Western",
        
        # 유럽음식
        "유럽": "European",
        "유럽음식": "European",
        "european": "European",
        
        # 이탈리안
        "이탈리안": "Italian",
        "이탈리아": "Italian",
        "italian": "Italian",
        
        # 멕시칸
        "멕시칸": "Mexican",
        "멕시코": "Mexican",
        "mexican": "Mexican",
        
        # 태국음식
        "태국": "Thai",
        "태국음식": "Thai",
        "thai": "Thai",
        
        # 인도음식
        "인도": "Indian",
        "인도음식": "Indian",
        "indian": "Indian",
        
        # 프랑스음식
        "프랑스": "French",
        "프랑스음식": "French",
        "french": "French",
    }
    
    # 쿼리에서 음식 종류 키워드 찾기
    detected_cuisine = None
    for keyword, cuisine_keyword in cuisine_mapping.items():
        if keyword.lower() in query_lower:
            detected_cuisine = cuisine_keyword
            logger.info(f"[extract_cuisine_type] 음식 종류 감지: '{keyword}' → '{cuisine_keyword}'")
            break
    
    return detected_cuisine, query


###########################################
# 2) 쿼리 번역 (한글 → 영어)
###########################################

def translate_query_to_english(query: str) -> str:
    """
    한글 쿼리를 영어로 번역 (BM25 검색을 위해)
    
    Args:
        query: 검색 쿼리 (한글 또는 영어)
        
    Returns:
        영어로 번역된 쿼리
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 이미 영어로 보이면 그대로 반환
    if all(ord(c) < 128 for c in query):
        logger.info(f"[translate_query] 이미 영어로 보입니다: '{query}'")
        return query
    
    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning("[translate_query] OPENROUTER_API_KEY가 없어 번역을 건너뜁니다.")
            return query
        
        # OpenRouter API 엔드포인트 (올바른 URL 사용)
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/langchain-ai/langgraph"),
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "LangGraph Agent"),
        }
        
        # 간단하고 빠른 번역 프롬프트
        prompt = f"""Translate the following Korean restaurant search query to English. 
Only return the translated query without any explanation or additional text.

Query: {query}

Translated query:"""
        
        # 더 안정적인 모델 사용 (여러 옵션 시도)
        # 참고: OpenRouter에서 무료 모델은 모델 이름에 :free를 붙이지 않음
        model_options = [
            "openai/gpt-oss-20b:free"
            "qwen/qwen-2.5-7b-instruct:free",  # 안정적인 무료 모델
            "meta-llama/llama-3.2-3b-instruct:free",  # 대안 무료 모델
        ]
        
        logger.info(f"[translate_query] 번역 시작: '{query}'")
        
        last_error = None
        for model in model_options:
            try:
                data = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 50
                }
                
                logger.info(f"[translate_query] 모델 시도: {model}")
                response = requests.post(url, headers=headers, json=data, timeout=10)
                
                # 404 에러면 다른 모델 시도
                if response.status_code == 404:
                    logger.warning(f"[translate_query] 모델 {model} 404 에러, 다음 모델 시도")
                    last_error = f"Model {model} not found (404)"
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                translated = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                # 따옴표 제거
                translated = translated.strip('"\'')
                
                if translated:
                    logger.info(f"[translate_query] 번역 완료 ({model}): '{query}' → '{translated}'")
                    return translated
                else:
                    logger.warning(f"[translate_query] 번역 결과가 비어있음 (모델: {model})")
                    continue
                    
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.warning(f"[translate_query] 모델 {model} 404 에러: {str(e)}")
                    last_error = str(e)
                    continue
                else:
                    logger.warning(f"[translate_query] HTTP 에러 ({model}): {str(e)}")
                    last_error = str(e)
                    continue
            except Exception as e:
                logger.warning(f"[translate_query] 에러 ({model}): {str(e)}")
                last_error = str(e)
                continue
        
        # 모든 모델 실패
        logger.warning(f"[translate_query] 모든 모델 실패, 원본 사용. 마지막 에러: {last_error}")
        return query
            
    except Exception as e:
        logger.warning(f"[translate_query] 번역 실패 (원본 사용): {str(e)}")
        return query


###########################################
# 2) 기존 ES Sparse Search (BM25)
###########################################
def get_es_client() -> Elasticsearch:
    host = os.getenv("ES_HOST", "http://localhost:9200")
    api_key = os.getenv("ES_API_KEY")
    return Elasticsearch(hosts=[host], api_key=api_key)

def search_es(query: str, index: str | None = None, size: int = 5):
    """
    ES BM25 기반 Sparse 검색
    실제 식당 데이터 필드명 사용
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[search_es] 검색 시작: query='{query}', size={size}")
        
        es = get_es_client()
        if es is None:
            raise RuntimeError("Elasticsearch 클라이언트를 생성할 수 없습니다. elasticsearch 패키지가 설치되어 있는지 확인하세요.")
        
        index = index or os.getenv("ES_INDEX", "restaurant_docs")
        logger.info(f"[search_es] ES Host: {os.getenv('ES_HOST')}, Index: {index}")
        
        # 음식 종류 추출 (한식, 일식, 중식 등)
        cuisine_type, _ = extract_cuisine_type(query)
        
        # 쿼리를 영어로 번역 (데이터가 영어로 되어있을 수 있음)
        translated_query = translate_query_to_english(query)
        
        if translated_query != query:
            logger.info(f"[search_es] 번역된 쿼리로 검색: '{query}' → '{translated_query}'")
        
        # 번역된 쿼리에서도 음식 종류 확인 (번역 후 영어 키워드가 나올 수 있음)
        if not cuisine_type:
            cuisine_type, _ = extract_cuisine_type(translated_query)
        
        # 음식 종류에 맞는 키워드 추가
        if cuisine_type:
            logger.info(f"[search_es] {cuisine_type} 음식 검색 감지: cuisines 필드 필터링 적용")
            # 쿼리에 해당 음식 키워드 추가 (없는 경우)
            if cuisine_type.lower() not in translated_query.lower():
                translated_query = f"{cuisine_type} {translated_query}"
                logger.info(f"[search_es] 쿼리 보강: '{translated_query}'")
        
        # 실제 필드명에 맞춰 검색 (소문자+언더스코어)
        # 특정 음식 종류 검색인 경우 cuisines 필드에 해당 키워드가 반드시 포함되어야 함 (must 필터)
        if cuisine_type:
            body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": {
                                    "cuisines": {
                                        "query": cuisine_type,  # 감지된 음식 종류 (Korean, Japanese, Chinese 등)
                                        "operator": "or"  # cuisines에 해당 키워드가 포함되어야 함
                                    }
                                }
                            }
                        ],
                        "should": [
                            {
                                "match": {
                                    "cuisines": {
                                        "query": translated_query,
                                        "boost": 3.0
                                    }
                                }
                            },
                            {
                                "multi_match": {
                                    "query": translated_query,
                                    "fields": [
                                        "restaurant_name^2",
                                        "text_content^2",
                                        "city^2",
                                        "address",
                                        "locality",
                                        "locality_verbose"
                                    ],
                                    "type": "best_fields",
                                    "operator": "or"
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": size
            }
        else:
            # 일반 검색 (한국음식 검색이 아닌 경우)
            body = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "cuisines": {
                                        "query": translated_query,
                                        "boost": 3.0
                                    }
                                }
                            },
                            {
                                "multi_match": {
                                    "query": translated_query,
                                    "fields": [
                                        "restaurant_name^2",
                                        "text_content^2",
                                        "city^2",
                                        "address",
                                        "locality",
                                        "locality_verbose"
                                    ],
                                    "type": "best_fields",
                                    "operator": "or"
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": size
            }
        
        logger.info(f"[search_es] ES 쿼리 실행 중... (쿼리: {translated_query})")
        
        # 디버깅: 인덱스 문서 개수 확인
        try:
            count_result = es.count(index=index)
            total_docs = count_result.get("count", 0)
            logger.info(f"[search_es] 인덱스 '{index}' 총 문서 개수: {total_docs:,}개")
            
            if total_docs == 0:
                logger.warning(f"[search_es] ⚠️  인덱스에 데이터가 없습니다!")
        except Exception as e:
            logger.warning(f"[search_es] 문서 개수 확인 실패: {e}")
        
        res = es.search(index=index, body=body)
        hits = res.get("hits", {}).get("hits", [])
        total_hits = res.get("hits", {}).get("total", {})
        
        if isinstance(total_hits, dict):
            total_hits_value = total_hits.get("value", 0)
        else:
            total_hits_value = total_hits
        
        logger.info(f"[search_es] ES 검색 완료: {len(hits)}개 결과 (전체 매칭: {total_hits_value}개)")
        
        # 결과가 없으면 샘플 문서 확인
        if len(hits) == 0:
            logger.warning(f"[search_es] 검색 결과가 없습니다. 샘플 문서 확인 중...")
            try:
                sample_res = es.search(index=index, body={"size": 1, "query": {"match_all": {}}})
                sample_hits = sample_res.get("hits", {}).get("hits", [])
                if sample_hits:
                    sample_source = sample_hits[0]["_source"]
                    logger.info(f"[search_es] 샘플 문서 필드명: {list(sample_source.keys())[:10]}")
                else:
                    logger.warning(f"[search_es] 샘플 문서도 없습니다. 인덱스가 비어있을 수 있습니다.")
            except Exception as e:
                logger.warning(f"[search_es] 샘플 문서 확인 실패: {e}")
        
        results = [
            {"id": h["_id"], "score": h["_score"], "source": h["_source"]}
            for h in hits
        ]
        
        return results
        
    except Exception as e:
        import traceback
        error_msg = f"ES 검색 실패: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"[search_es] {error_msg}")
        raise RuntimeError(error_msg) from e

###########################################
# 3) OpenRouter bge-m3 임베딩 생성 및 ES KNN Dense Search
###########################################

def get_embedding_from_openrouter(query: str) -> List[float]:
    """
    OpenRouter API를 사용하여 bge-m3 임베딩 생성
    
    Args:
        query: 임베딩할 텍스트
        
    Returns:
        임베딩 벡터 (리스트)
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")
    
    model_name = os.getenv("OPENROUTER_EMBEDDING_MODEL", "baai/bge-m3")
    
    url = "https://openrouter.ai/api/v1/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", ""),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "LangGraph Agent"),
    }
    
    data = {
        "model": model_name,
        "input": query
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # OpenRouter 응답 형식: {"data": [{"embedding": [...]}]}
        if "data" in result and len(result["data"]) > 0:
            return result["data"][0]["embedding"]
        else:
            raise ValueError(f"Unexpected response format: {result}")
            
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"OpenRouter API 호출 실패: {str(e)}")


def dense_search(query: str, index: str | None = None, size: int = 5) -> List[Dict[str, Any]]:
    """
    bge-m3 임베딩 기반 ES KNN Dense Search
    
    Args:
        query: 검색 쿼리
        index: ES 인덱스명 (None이면 환경변수에서 가져옴)
        size: 반환할 결과 개수
        
    Returns:
        [{"id": str, "score": float, "source": dict}, ...]
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[dense_search] 검색 시작: query='{query}', size={size}")
        
        es = get_es_client()
        if es is None:
            raise RuntimeError("Elasticsearch 클라이언트를 생성할 수 없습니다.")
        
        index = index or os.getenv("ES_INDEX", "restaurant_docs")
        logger.info(f"[dense_search] ES Host: {os.getenv('ES_HOST')}, Index: {index}")
        
        # OpenRouter로 쿼리 임베딩 생성
        logger.info("[dense_search] OpenRouter로 임베딩 생성 중...")
        query_vector = get_embedding_from_openrouter(query)
        logger.info(f"[dense_search] 임베딩 생성 완료: 차원={len(query_vector)}")
        
        # ES KNN 검색 (search API에 knn 쿼리 포함)
        logger.info("[dense_search] ES KNN 검색 실행 중...")
        body = {
            "knn": {
                "field": "embedding",  # 일반적으로 많이 쓰는 필드명
                "query_vector": query_vector,
                "k": size,
                "num_candidates": size * 2  # 후보 개수 (정확도와 성능의 균형)
            }
        }
        
        response = es.search(index=index, body=body)
        
        hits = response.get("hits", {}).get("hits", [])
        logger.info(f"[dense_search] ES KNN 검색 완료: {len(hits)}개 결과")
        
        results = [
            {
                "id": h["_id"],
                "score": float(h["_score"]),
                "source": h["_source"],
            }
            for h in hits
        ]
        
        return results
        
    except Exception as e:
        import traceback
        error_msg = f"ES KNN 검색 실패: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"[dense_search] {error_msg}")
        raise RuntimeError(error_msg) from e




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