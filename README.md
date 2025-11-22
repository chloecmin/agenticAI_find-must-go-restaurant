# 고려대학교 빅데이터와정보검색 팀 프로젝트 : Find Must Go Restaurant
---
## 프로젝트 INFO
- 개요 : AgenticAI 기반 맛집검색엔진 구축
- 기간 : 2025.11.19 ~
- 참여자 : 민채정, 심기성, 이윤주, 권지수
---
## How to run
1. requirements.txt 실행
```bash
pip install -r requirements.txt
```

2. 환경 변수 설정
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

# -------- Google Place INFO --------
GOOGLE_PLACES_API_KEY="your Key"
GOOGLE_PLACES_REGION="your region"
```
---