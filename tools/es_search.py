import os
import math
import csv
from pathlib import Path
from typing import List, Dict, Any

# 기존 ElasticSearch import
try:
    from elasticsearch import Elasticsearch
except ImportError:
    Elasticsearch = None

###########################################
# 1) 기존 ES Sparse Search (BM25)
###########################################
def get_es_client() -> Elasticsearch:
    host = os.getenv("ES_HOST", "http://localhost:9200")
    api_key = os.getenv("ES_API_KEY")
    return Elasticsearch(hosts=[host], api_key=api_key)

def search_es(query: str, index: str | None = None, size: int = 5):
    es = get_es_client()
    index = index or os.getenv("ES_INDEX", "restaurant_docs")

    body = {
        "query": {
            "multi_match": {
                "query": query,
                "fields": ["title^2", "content", "body", "text"],
                "type": "best_fields"
            }
        },
        "size": size
    }

    res = es.search(index=index, body=body)
    hits = res.get("hits", {}).get("hits", [])

    return [
        {"id": h["_id"], "score": h["_score"], "source": h["_source"]}
        for h in hits
    ]


###########################################
# 2) CSV 기반 BM25 테스트 검색
###########################################
# (여기 BM25 관련 함수들이 쭉 있음 — 그대로 두면 됨)
# _tokenize()
# _build_bm25_index()
# _bm25_score()
# search_es_csv_bm25()
###########################################



###########################################
# 3) 🔥 너가 작성해야 하는 Dense Search 추가
###########################################

from sentence_transformers import SentenceTransformer
import numpy as np

# bge-m3 모델 로드
embedding_model = SentenceTransformer("BAAI/bge-m3")

def embed_query(query: str) -> list[float]:
    """Query 문장을 bge-m3 임베딩으로 변환"""
    embeddings = embedding_model.encode(query, normalize_embeddings=True)
    return embeddings.tolist()


def dense_search(query: str, size: int = 5):
    """bge-m3 임베딩 기반 knn Dense Search"""
    es = get_es_client()  # ✔ 기존 client 재사용

    query_vector = embed_query(query)

    response = es.knn_search(
        index=os.getenv("ES_INDEX"),
        knn={
            "field": "embedding",
            "query_vector": query_vector,
            "k": size,
            "num_candidates": size * 2
        }
    )

    hits = response["hits"]["hits"]

    return [
        {
            "id": h["_id"],
            "score": h["_score"],
            "source": h["_source"],
        }
        for h in hits
    ]

###########################################
# 여기까지가 es_search.py 최종본!
###########################################
