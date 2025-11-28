import os
import csv
from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer

# -----------------------------
# 1) 환경변수 읽기
# -----------------------------
ES_HOST = os.getenv("ES_HOST")
ES_API_KEY = os.getenv("ES_API_KEY")
ES_INDEX = os.getenv("ES_INDEX")

if not ES_HOST or not ES_API_KEY:
    raise RuntimeError("❌ ES_HOST 또는 ES_API_KEY 환경변수가 없습니다. .env 파일을 확인하세요!")

# Elasticsearch 클라이언트
es = Elasticsearch(
    ES_HOST,
    api_key=ES_API_KEY,
)

# -----------------------------
# 2) 임베딩 모델 로드 (bge-m3)
# -----------------------------
print("📌 bge-m3 모델 로딩 중...")
embedding_model = SentenceTransformer("BAAI/bge-m3")
print("✅ bge-m3 모델 로드 완료!")

# -----------------------------
# 3) CSV 업로드 + 임베딩 생성
# -----------------------------
def upload_data():
    csv_path = "data/restaurants_mock.csv"
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"❌ CSV 파일을 찾을 수 없습니다: {csv_path}")

    docs = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Search용 텍스트 생성 (name + area + category + keywords + review_snippet)
            text = f"{row.get('name', '')} {row.get('area', '')} {row.get('category', '')} {row.get('keywords', '')} {row.get('review_snippet', '')}"

            # bge-m3 임베딩 생성
            embedding = embedding_model.encode(text, normalize_embeddings=True).tolist()

            # Elasticsearch에 넣을 문서 구성
            row["embedding"] = embedding  # 🔥 Dense Search의 핵심

            docs.append({
                "_index": ES_INDEX,
                "_source": row,
            })

    # Bulk 업로드
    helpers.bulk(es, docs)
    print(f"🔥 업로드 완료! 총 문서: {len(docs)}")


if __name__ == "__main__":
    upload_data()
