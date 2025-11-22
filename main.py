# 환경변수를 가장 먼저 로드 (모든 import 전에 실행)
from dotenv import load_dotenv
load_dotenv()

import argparse
import asyncio
from graph.builder import build_graph


async def run_streaming(user_query: str):
    graph = build_graph()

    # 초기 상태
    state = {
        "user_query": user_query,
        "history": [],
        "plan": "",
        "search_query": "",
        "search_results": [],
        "answer": "",
    }

    print("=== LangGraph Streaming Start ===")
    async for event in graph.astream(state):
        # event는 {"coordinator": {...}}, {"planner": {...}} 이런 식의 delta
        for node_name, node_state in event.items():
            print(f"\n--- [{node_name}] ---")
            # 마지막 answer만 출력하고 싶다면 조건 걸어도 됨
            answer = node_state.get("answer")
            plan = node_state.get("plan")
            if plan:
                print("[plan]", plan[:300])
            if answer:
                print("[answer]", answer[:500])

    print("\n=== Streaming Finished ===")


def run_once(user_query: str):
    graph = build_graph()
    state = {
        "user_query": user_query,
        "history": [],
        "plan": "",
        "search_query": "",
        "search_results": [],
        "answer": "",
    }
    final_state = graph.invoke(state)
    print("\n=== Final Answer ===\n")
    print(final_state["answer"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangGraph Agentic RAG Demo")
    parser.add_argument("--user_query", type=str, required=True, help="사용자 질문")
    parser.add_argument("--stream", action="store_true", help="스트리밍 모드로 실행")
    args = parser.parse_args()

    if args.stream:
        asyncio.run(run_streaming(args.user_query))
    else:
        run_once(args.user_query)