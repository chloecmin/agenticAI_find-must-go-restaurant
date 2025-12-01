from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from graph.builder import build_graph
from uuid import uuid4
import json
import asyncio

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


@app.post("/query/stream")
async def get_recommendation_stream(request: QueryRequest):
    """
    사용자 쿼리를 받아 맛집 추천 답변을 스트리밍 방식으로 반환합니다.

    - session_id를 받으면 해당 세션의 대화 기록이 유지됩니다.
    - session_id가 없으면 새로운 세션을 생성합니다.
    - Server-Sent Events (SSE) 형식으로 응답합니다.
    """
    # session_id가 없으면 새로 생성
    session_id = request.session_id or f"session-{uuid4()}"

    async def event_generator():
        try:
            # 첫 번째로 session_id 전송
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

            # 이번 턴에서 설정할 상태
            state = {
                "user_query": request.user_query,
            }

            # thread_id로 세션 구분
            config = {"configurable": {"thread_id": session_id}}

            # 스트리밍 실행
            async for event in graph.astream(state, config=config):
                # event는 {"node_name": {...}} 형식
                for node_name, node_state in event.items():
                    # 각 노드의 상태를 스트리밍
                    event_data = {
                        "type": "node_update",
                        "node": node_name,
                        "data": {}
                    }

                    # final_answer가 있으면 전송
                    if "final_answer" in node_state:
                        event_data["data"]["final_answer"] = node_state["final_answer"]
                        yield f"data: {json.dumps(event_data)}\n\n"

                    # plan이 있으면 전송
                    elif "plan" in node_state and node_state["plan"]:
                        event_data["data"]["plan"] = node_state["plan"]
                        yield f"data: {json.dumps(event_data)}\n\n"

                    # answer가 있으면 전송
                    elif "answer" in node_state and node_state["answer"]:
                        event_data["data"]["answer"] = node_state["answer"]
                        yield f"data: {json.dumps(event_data)}\n\n"

                # 약간의 딜레이 (클라이언트가 이벤트를 처리할 수 있도록)
                await asyncio.sleep(0.01)

            # 완료 이벤트 전송
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        except Exception as e:
            # 에러 발생 시 에러 이벤트 전송
            error_data = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 비활성화
        }
    )


@app.get("/")
async def root():
    """
    API 상태 확인
    """
    return {"message": "맛집 추천 API가 정상 작동 중입니다.", "docs": "/docs"}