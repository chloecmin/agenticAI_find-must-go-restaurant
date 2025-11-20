from langgraph.graph import StateGraph, END

from .nodes import (
    AgentState,
    coordinator_node,
    planner_node,
    tool_agent_node,
    supervisor_node,
    evaluator_node,
)


def eval_router(state: AgentState) -> str:
    """
    evaluator에서 다음으로 어디로 갈지 결정:
    - needs_revision=True 이고 loop_count < 2 → coordinator로 다시
    - 아니면 종료
    """
    needs_revision = state.get("needs_revision", False)
    loop = state.get("loop_count", 0)

    if needs_revision and loop < 2:
        return "retry"
    return "end"


def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("tool_agent", tool_agent_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("evaluator", evaluator_node)

    workflow.set_entry_point("coordinator")

    workflow.add_edge("coordinator", "planner")
    workflow.add_edge("planner", "tool_agent")
    workflow.add_edge("tool_agent", "supervisor")
    workflow.add_edge("supervisor", "evaluator")

    workflow.add_conditional_edges(
        "evaluator",
        eval_router,
        {
            "retry": "coordinator",
            "end": END,
        },
    )

    return workflow.compile()
