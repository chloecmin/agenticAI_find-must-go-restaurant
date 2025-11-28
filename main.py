# 환경변수를 가장 먼저 로드 (모든 import 전에 실행)
from dotenv import load_dotenv
load_dotenv()
from uuid import uuid4

import argparse
import asyncio
from graph.builder import build_graph


# MemorySaver가 붙은 LangGraph 앱을 전역으로 한 번만 생성
app = build_graph()


async def chat_streaming(initial_user_query: str | None = None,
                         thread_id: str | None = None):
    """
    비동기 스트리밍 모드로 여러 턴 대화를 처리하는 채팅 루프.
    - 하나의 Python 프로세스 안에서 여러 번 app.astream(...)을 호출
    - 같은 thread_id를 계속 사용하므로 MemorySaver 기반 세션 상태가 유지된다.
    """
    # thread_id가 없으면 새로 생성 (새 세션)
    if thread_id is None:
        thread_id = f"stream-{uuid4()}"

    print(f"=== LangGraph Streaming Chat Start (thread_id={thread_id}) ===")
    print("대화를 종료하려면 '/exit' 를 입력하세요.\n")

    # 첫 턴: CLI에서 --user_query 로 받은 값이 있으면 그걸 사용
    first_turn = True
    user_query = initial_user_query

    while True:
        # 첫 턴이 아니면 사용자에게 새 질문 입력 받기
        if not first_turn:
            try:
                user_query = input("\n사용자 질문: ").strip()
            except EOFError:
                # Ctrl+D 등으로 입력 스트림이 끊긴 경우
                print("\n[입력 종료 감지, 채팅을 종료합니다.]")
                break

        # 빈 문자열이거나 /exit 이면 종료
        if not user_query or user_query.lower() in ("/exit", "exit", "quit"):
            print("\n[채팅 종료 요청 감지, 종료합니다.]")
            break

        # 이번 턴에서 "새로 세팅"할 값만 넣기 (AgentState의 부분집합)
        state = {
            "user_query": user_query,
            # history / session_memory / user_profile / last_reco 등은 건드리지 않음
            # → 이미 있는 값은 MemorySaver가 불러오고
            # → 없는 값은 각 노드에서 state.get(..., 기본값)으로 처리
        }

        config = {"configurable": {"thread_id": thread_id}}

        print(f"\n=== LangGraph Streaming Turn (thread_id={thread_id}) ===")
        print(f"[질문] {user_query}\n")

        # 비동기 스트리밍 실행
        async for event in app.astream(state, config=config):
            # event는 {"coordinator": {...}}, {"planner": {...}} 이런 식의 delta
            for node_name, node_state in event.items():
                final_answer = node_state.get("final_answer")
                if final_answer:
                    print("\n--- [최종 답변] ---")
                    print(final_answer[:2000])  # 너무 길면 앞부분만 잘라서 표시

        print("\n=== Turn Finished ===")

        # 첫 턴 처리 완료
        first_turn = False

    print(f"\n=== Streaming Chat Finished (thread_id={thread_id}) ===")

# async def run_streaming(user_query: str):
#     graph = build_graph()

#     # 초기 상태
#     state = {
#         "user_query": user_query,
#         "history": [],
#         "plan": "",
#         "search_query": "",
#         "search_results": [],
#         "answer": "",
#     }

#     print("=== LangGraph Streaming Start ===")
#     async for event in graph.astream(state):
#         # event는 {"coordinator": {...}}, {"planner": {...}} 이런 식의 delta
#         for node_name, node_state in event.items():
#             print(f"\n--- [{node_name}] ---")
#             # 마지막 answer만 출력하고 싶다면 조건 걸어도 됨
#             answer = node_state.get("answer")
#             plan = node_state.get("plan")
#             if plan:
#                 print("[plan]", plan[:300])
#             if answer:
#                 print("[answer]", answer[:500])

#     print("\n=== Streaming Finished ===")


def run_once(user_query: str, thread_id: str | None = None):
    """
    한 번만 실행해서 최종 답변을 출력하는 모드 (동기 방식).
    같은 thread_id로 여러 번 호출하면 세션 단위 Short-term Memory가 유지되지만,
    이 함수 자체는 한 턴만 처리한다.
    """
    # thread_id가 없으면 새로 생성 (새 세션)
    if thread_id is None:
        thread_id = f"run-{uuid4()}"

    # 이번 턴에서 설정할 상태 (AgentState의 부분집합)
    state = {
        "user_query": user_query,
    }

    config = {"configurable": {"thread_id": thread_id}}

    final_state = app.invoke(state, config=config)

    print(f"\n=== Final Answer (thread_id={thread_id}) ===\n")
    print(final_state.get("final_answer", "답변을 생성하지 못했습니다."))
    print(f"\n[thread_id] {thread_id}")


# def run_once(user_query: str):
#     graph = build_graph()
#     state = {
#         "user_query": user_query,
#         "history": [],
#         "plan": "",
#         "search_query": "",
#         "search_results": [],
#         "answer": "",
#     }
#     final_state = graph.invoke(state)
#     print("\n=== Final Answer ===\n")
#     print(final_state["answer"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangGraph 맛집 추천 Agentic AI")
    parser.add_argument("--user_query", type=str, required=False,
                        help="사용자 질문 (stream 모드에서는 첫 질문으로 사용 가능)")
    parser.add_argument("--stream", action="store_true", help="스트리밍 채팅 모드로 실행")
    parser.add_argument(
        "--thread_id",
        type=str,
        default=None,
        help="세션을 구분하는 thread_id (같은 값을 주면 MemorySaver로 상태가 이어집니다.)",
    )
    args = parser.parse_args()

    if args.stream:
        # 비동기 스트리밍 채팅 루프 시작
        asyncio.run(chat_streaming(args.user_query, args.thread_id))
    else:
        # 단일 턴 실행 (동기)
        if not args.user_query:
            raise SystemExit("--user_query 는 non-stream 모드에서 필수입니다.")
        run_once(args.user_query, args.thread_id)
