from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from graph.builder import build_graph
from uuid import uuid4

app = FastAPI(
    title="맛집 추천 API",
    description="사용자 쿼리를 받아 맛집을 추천하는 AI 에이전트 API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 앱 초기화 시 한 번만 그래프 생성
graph = build_graph()


class QueryRequest(BaseModel):
    user_query: str
    session_id: str | None = None  # 세션 ID 추가 (선택적)

    class Config:
        json_schema_extra = {
            "example": {
                "user_query": "강남에서 맛있는 이탈리안 레스토랑 추천해줘",
                "session_id": "unique-session-id-123"
            }
        }


class QueryResponse(BaseModel):
    answer: str
    session_id: str  # 세션 ID 반환


@app.post("/query", response_model=QueryResponse)
async def get_recommendation(request: QueryRequest):
    """
    사용자 쿼리를 받아 맛집 추천 답변을 반환합니다.

    - session_id를 받으면 해당 세션의 대화 기록이 유지됩니다.
    - session_id가 없으면 새로운 세션을 생성합니다.
    """
    # session_id가 없으면 새로 생성
    session_id = request.session_id or f"session-{uuid4()}"

    # 이번 턴에서 설정할 상태
    state = {
        "user_query": request.user_query,
    }

    # thread_id로 세션 구분 (MemorySaver가 이 ID로 상태를 저장/불러옴)
    config = {"configurable": {"thread_id": session_id}}

    # 그래프 실행
    final_state = graph.invoke(state, config=config)
    answer = final_state.get("final_answer", "답변을 생성하지 못했습니다.")

    return QueryResponse(answer=answer, session_id=session_id)


@app.get("/")
async def root():
    """
    API 상태 확인
    """
    return {"message": "맛집 추천 API가 정상 작동 중입니다.", "docs": "/docs"}