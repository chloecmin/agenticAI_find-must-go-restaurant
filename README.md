# Find Must Go Restaurant
---
## 프로젝트 INFO
- 개요 : 고려대학교 SW·AI융합대학원 팀프로젝트
- 과목 : 빅데이터와 정보검색색
- 주제 : AgenticAI 기반 맛집검색엔진 구축
- 기간 : 2025.11.19 ~
- 참여자 : 권지수, 민채정, 심기성, 이윤주
- 교수님 : 황영숙교수님
---
## How to run
1. requirements.txt 실행
```bash
pip install -r requirements.txt
```

2. 환경 변수 설정  <br/>
프로젝트 루트에 `.env` 파일을 생성하고 다음 환경변수를 설정:
```bash
# -------- LLM API KEY --------
OPENAI_API_KEY="your Key"
OPENROUTER_API_KEY="your Key"
LANGCHAIN_API_KEY="your Key"

BASE_LLM_MODEL="your Model"
TOOL_LLM_MODEL="your Model"


# -------- ES INFO --------
ES_HOST="your Host address"
ES_INDEX="your index"
ES_API_KEY="your API key (optional)"

# -------- Embedding Model (for Hybrid Search) --------
OPENROUTER_EMBEDDING_MODEL="baai/bge-m3"  # 기본값: baai/bge-m3

# -------- Google Place INFO --------
GOOGLE_PLACES_API_KEY="your Key"
GOOGLE_PLACES_REGION="your region"
```

3. 실행
```bash
python main.py --user_query "홍대에서 우동 맛집 찾고 2개 먹을 때 가격 알려줘"
``` 
---
