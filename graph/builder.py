from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .nodes import (
    AgentState,
    coordinator_node,
    planner_node,
    search_agent_node,
    places_agent_node,
    budget_agent_node,
    supervisor_node,
    evaluator_node,
    final_output_node,
)


def planner_router(state: AgentState) -> str:
    """
    planner에서 처음 호출될 때 어떤 sub agent를 시작할지 결정.
    planner에서는 절대 supervisor로 가지 않고, 항상 sub agent 중 하나를 선택.
    """
    tool_mode = state.get("tool_mode", "mixed")
    user_query = state.get("user_query", "").lower()
    subtask = state.get("subtask", "").lower()
    
    # 예산 관련 키워드
    budget_keywords = ["예산", "비용", "가격", "돈", "얼마", "계산"]
    needs_budget = (
        tool_mode == "budget"
        or "budget" in tool_mode
        or any(keyword in user_query for keyword in budget_keywords)
        or any(keyword in subtask for keyword in budget_keywords)
    )
    
    # 맛집 검색 관련 키워드
    search_keywords = ["맛집", "식당", "추천", "찾아", "검색", "근처"]
    needs_search = any(keyword in user_query for keyword in search_keywords) or any(
        keyword in subtask for keyword in search_keywords
    )
    
    # 리뷰/상세 정보 관련 키워드
    review_keywords = ["리뷰", "평점", "후기", "어때", "추천할만", "정보"]
    needs_review = any(keyword in user_query for keyword in review_keywords) or any(
        keyword in subtask for keyword in review_keywords
    )
    
    # 특정 식당 이름이 명확히 언급된 경우
    specific_restaurant_keywords = ["텐동야", "파스타노바", "비스트로온", "돈카츠모노", "김치찌개연구소"]
    has_specific_restaurant = any(keyword in user_query for keyword in specific_restaurant_keywords) or any(
        keyword in subtask for keyword in specific_restaurant_keywords
    )
    
    # 실행 순서 결정 (planner에서는 항상 sub agent 중 하나를 선택)
    
    # 1. 예산 계산이 필요한 경우
    if needs_budget:
        return "budget_agent"
    
    # 2. 특정 식당이 명시된 경우 → places_agent부터 시작
    if has_specific_restaurant:
        return "places_agent"
    
    # 3. 일반 맛집 검색 → search_agent부터 시작
    if needs_search:
        return "search_agent"
    
    # 4. 리뷰가 필요한 경우 → places_agent (하지만 search가 먼저 필요할 수 있음)
    if needs_review:
        return "places_agent"
    
    # 5. 기본값: search_agent부터 시작
    return "search_agent"


def sub_agent_router(state: AgentState) -> str:
    """
    sub agent들에서 다음 단계를 결정하는 router.
    필요한 sub agent가 더 있으면 계속 실행하고, 모두 완료되면 supervisor로 이동.
    """
    tool_mode = state.get("tool_mode", "mixed")
    user_query = state.get("user_query", "").lower()
    subtask = state.get("subtask", "").lower()
    
    # 예산 관련 키워드
    budget_keywords = ["예산", "비용", "가격", "돈", "얼마", "계산"]
    needs_budget = (
        tool_mode == "budget"
        or "budget" in tool_mode
        or any(keyword in user_query for keyword in budget_keywords)
        or any(keyword in subtask for keyword in budget_keywords)
    )
    
    # 맛집 검색 관련 키워드
    search_keywords = ["맛집", "식당", "추천", "찾아", "검색", "근처"]
    needs_search = any(keyword in user_query for keyword in search_keywords) or any(
        keyword in subtask for keyword in search_keywords
    )
    
    # 리뷰/상세 정보 관련 키워드
    review_keywords = ["리뷰", "평점", "후기", "어때", "추천할만", "정보"]
    needs_review = any(keyword in user_query for keyword in review_keywords) or any(
        keyword in subtask for keyword in review_keywords
    )
    
    # 특정 식당 이름이 명확히 언급된 경우
    specific_restaurant_keywords = ["텐동야", "파스타노바", "비스트로온", "돈카츠모노", "김치찌개연구소"]
    has_specific_restaurant = any(keyword in user_query for keyword in specific_restaurant_keywords) or any(
        keyword in subtask for keyword in specific_restaurant_keywords
    )
    
    # 현재 실행 상태 확인
    tool_trace = state.get("tool_trace", "")
    has_search_result = "[Search Agent 결과]" in tool_trace
    has_places_result = "[Places Agent 결과]" in tool_trace
    has_budget_result = "[Budget Agent 결과]" in tool_trace
    
    # 실행 순서 결정
    
    # 1. 예산 계산이 필요한 경우
    if needs_budget and not has_budget_result:
        return "budget_agent"
    
    # 2. 특정 식당이 명시된 경우
    if has_specific_restaurant:
        if not has_places_result:
            return "places_agent"
        elif needs_budget and not has_budget_result:
            return "budget_agent"
        else:
            return "supervisor"  # 모든 필요한 agent 실행 완료
    
    # 3. 일반 맛집 검색
    if needs_search and not has_search_result:
        return "search_agent"
    
    # 4. search_agent 결과가 있으면 places_agent 실행
    if has_search_result and not has_places_result:
        return "places_agent"
    
    # 5. 리뷰가 필요한 경우 places_agent 실행
    if needs_review and not has_places_result:
        return "places_agent"
    
    # 6. 모든 필요한 agent 실행 완료
    return "supervisor"


def eval_router(state: AgentState) -> str:
    """
    evaluator에서 다음으로 어디로 갈지 결정:
    - needs_revision=True 이고 loop_count < 3 → coordinator로 다시 (최대 3번: 첫 실행 + 재시도 2번)
    - needs_revision=False → final_output으로 가서 답변 출력
    """
    needs_revision = state.get("needs_revision", False)
    loop = state.get("loop_count", 0)

    if needs_revision and loop < 3:
        return "retry"
    return "final_output"


def build_graph():
    workflow = StateGraph(AgentState)

    # Super Agent Layer
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("final_output", final_output_node)
    
    # Sub Agent Layer
    workflow.add_node("search_agent", search_agent_node)
    workflow.add_node("places_agent", places_agent_node)
    workflow.add_node("budget_agent", budget_agent_node)

    workflow.set_entry_point("coordinator")

    # Super Agent Flow
    workflow.add_edge("coordinator", "planner")
    
    # Planner에서 Sub Agent 선택 (절대 supervisor로 가지 않음)
    workflow.add_conditional_edges(
        "planner",
        planner_router,
        {
            "search_agent": "search_agent",
            "places_agent": "places_agent",
            "budget_agent": "budget_agent",
        },
    )
    
    # Sub Agent들에서 다음 단계로
    workflow.add_conditional_edges(
        "search_agent",
        sub_agent_router,
        {
            "places_agent": "places_agent",
            "budget_agent": "budget_agent",
            "supervisor": "supervisor",
        },
    )
    
    workflow.add_conditional_edges(
        "places_agent",
        sub_agent_router,
        {
            "budget_agent": "budget_agent",
            "supervisor": "supervisor",
        },
    )
    
    workflow.add_conditional_edges(
        "budget_agent",
        sub_agent_router,
        {
            "search_agent": "search_agent",
            "places_agent": "places_agent",
            "supervisor": "supervisor",
        },
    )
    
    # Supervisor → Evaluator
    workflow.add_edge("supervisor", "evaluator")

    # Evaluator에서 최종 결정
    workflow.add_conditional_edges(
        "evaluator",
        eval_router,
        {
            "retry": "coordinator",
            "final_output": "final_output",
        },
    )
    
    workflow.add_edge("final_output", END)


    # MEMORY SAVER 추가
    memory = MemorySaver()

    # checkpointer 적용해 compile
    app = workflow.compile(checkpointer=memory)

    return app
