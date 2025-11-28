import os
from elasticsearch import Elasticsearch

ES_HOST = os.getenv("ES_HOST")
ES_API_KEY = os.getenv("ES_API_KEY")
INDEX_NAME = os.getenv("ES_INDEX")

settings = {
    "settings": {
        "analysis": {
            "analyzer": {
                "my_analyzer": {
                    "type": "standard"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "embedding": {
                "type": "dense_vector",
                "dims": 1024,
                "index": True,
                "similarity": "cosine"
            },
            "name": {"type": "text"},
            "area": {"type": "text"},
            "category": {"type": "text"},
            "address": {"type": "text"},
            "keywords": {"type": "text"},
            "rating": {"type": "float"},
            "user_ratings_total": {"type": "integer"},
            "review_snippet": {"type": "text"},
            "latitude": {"type": "float"},
            "longitude": {"type": "float"}
        }
    }
}
