from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from graph.builder import build_graph

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


class QueryRequest(BaseModel):
    user_query: str

    class Config:
        json_schema_extra = {
            "example": {
                "user_query": "강남에서 맛있는 이탈리안 레스토랑 추천해줘"
            }
        }


class QueryResponse(BaseModel):
    answer: str


@app.post("/query", response_model=QueryResponse)
async def get_recommendation(request: QueryRequest):
    """
    사용자 쿼리를 받아 맛집 추천 답변을 반환합니다.
    """
    graph = build_graph()

    state = {
        "user_query": request.user_query,
        "history": [],
    }

    config = {"configurable": {"thread_id": "api-request"}}

    final_state = graph.invoke(state, config=config)
    answer = final_state.get("final_answer", "답변을 생성하지 못했습니다.")

    return QueryResponse(answer=answer)


@app.get("/")
async def root():
    """
    API 상태 확인
    """
    return {"message": "맛집 추천 API가 정상 작동 중입니다.", "docs": "/docs"}