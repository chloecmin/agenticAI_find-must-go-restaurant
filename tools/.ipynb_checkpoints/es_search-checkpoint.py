import os
from typing import List, Dict, Any
from elasticsearch import Elasticsearch


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
