# agenticAI_find-must-go-restaurant

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 환경변수를 설정하세요:

### `.env` 파일 전체 예시

```bash
# ============================================
# 필수 환경변수
# ============================================

# OpenRouter API 키 (필수)
# 발급: https://openrouter.ai/keys
OPENROUTER_API_KEY=your_openrouter_api_key_here

# LangSmith API 키 (필수 - langgraph dev 사용 시)
# 발급: https://smith.langchain.com/settings
LANGCHAIN_API_KEY=your_langsmith_api_key_here

# ============================================
# 선택사항 환경변수
# ============================================

# LangSmith 추적 설정 (선택사항)
# langgraph dev를 사용할 때는 자동으로 활성화됨
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=agenticAI_find-must-go-restaurant

# OpenRouter 헤더 설정 (선택사항)
OPENROUTER_HTTP_REFERER=https://your-app-url.com
OPENROUTER_APP_NAME=LangGraph Agent

# Google Places API (선택사항)
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here
GOOGLE_PLACES_REGION=kr

# ElasticSearch 설정 (선택사항)
ES_HOST=http://localhost:9200
ES_INDEX=restaurant_docs

# 데이터 파일 경로
MENU_CSV_PATH=data/restaurant_menus_mock.csv
```

### 환경변수 상세 설명

### 필수 환경변수

```bash
# OpenRouter API 키 (필수)
# OpenRouter에서 발급: https://openrouter.ai/keys
OPENROUTER_API_KEY=your_openrouter_api_key_here

# LangSmith API 키 (필수 - langgraph dev 사용 시)
# LangSmith에서 발급: https://smith.langchain.com/settings
LANGCHAIN_API_KEY=your_langsmith_api_key_here
```

### 선택사항 환경변수

```bash
# LangSmith 추적 설정 (선택사항)
# langgraph dev를 사용할 때는 자동으로 활성화되지만, 직접 실행할 때는 아래 설정 필요
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=agenticAI_find-must-go-restaurant

# OpenRouter 헤더 설정 (선택사항)
OPENROUTER_HTTP_REFERER=https://your-app-url.com
OPENROUTER_APP_NAME=LangGraph Agent

# 기본 LLM 모델 (선택사항, coordinator/planner/supervisor/evaluator용)
# 기본값: qwen/qwen3-30b-a3b:free (rate limit 발생 시 다른 모델로 변경)
# 무료 대안: meta-llama/llama-3.1-8b-instruct, mistralai/mistral-7b-instruct
BASE_LLM_MODEL=qwen/qwen3-30b-a3b:free

# Tool Agent용 모델 (선택사항, tool use 지원 필수)
# 기본값: openai/gpt-4o-mini
# 가장 저렴한 옵션: openai/gpt-3.5-turbo
# qwen 같은 일부 무료 모델은 tool use를 지원하지 않으므로 주의
TOOL_LLM_MODEL=openai/gpt-3.5-turbo

# Google Places API (선택사항)
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here
GOOGLE_PLACES_REGION=kr

# ElasticSearch 설정 (선택사항)
ES_HOST=http://localhost:9200
ES_INDEX=restaurant_docs

# 데이터 파일 경로
MENU_CSV_PATH=data/restaurant_menus_mock.csv
```

### OpenRouter 모델 선택

#### 기본 LLM 모델
`agents/llm.py`의 `get_llm()` 함수에서 기본 모델을 변경할 수 있습니다.

#### Tool Use를 지원하는 모델 (필수)
`tool_agent`는 tool calling이 필요하므로, tool use를 지원하는 모델을 사용해야 합니다.

`.env` 파일에 다음을 추가하세요:
```bash
# Tool Agent용 모델 (tool use 지원 필수)
# 가장 저렴한 옵션: openai/gpt-3.5-turbo
# 기본값: openai/gpt-4o-mini
TOOL_LLM_MODEL=openai/gpt-3.5-turbo
```

**Tool Use를 지원하는 모델 예시:**

**상용 모델 (유료, 안정적):**
- `openai/gpt-3.5-turbo` ⭐ **가장 저렴한 옵션** (추천)
- `openai/gpt-4o-mini` (기본값, 가성비 좋음)
- `openai/gpt-4o` (더 강력하지만 비쌈)
- `anthropic/claude-3-opus` (고성능, 비쌈)
- `anthropic/claude-3-sonnet` (중간 가격)
- `google/gemini-pro` (중간 가격)

**오픈소스 모델 (일부 무료/저렴):**
- `meta-llama/llama-3.1-8b-instruct` (오픈소스, function calling 지원)
- `meta-llama/llama-3.1-70b-instruct` (오픈소스, 더 강력)
- `mistralai/mistral-7b-instruct` (오픈소스)
- `qwen/qwen-2.5-7b-instruct` (오픈소스, 일부 function calling 지원)
- `qwen/qwen-2.5-14b-instruct` (오픈소스)
- `deepseek/deepseek-chat` (오픈소스, function calling 지원)

**주의:** 
- `qwen/qwen3-30b-a3b:free` 같은 일부 무료 모델은 tool use를 지원하지 않습니다.
- 오픈소스 모델도 function calling 지원 여부는 모델마다 다르므로 OpenRouter 문서를 확인하세요.
- 오픈소스 모델은 성능이 상용 모델보다 낮을 수 있습니다.

전체 모델 목록: https://openrouter.ai/models