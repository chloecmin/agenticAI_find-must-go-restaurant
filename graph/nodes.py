import os
import json
import logging
from typing import TypedDict, List, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from prompts.template import apply_prompt_template
from tools.llm_tools import (
    es_search_tool,
    google_places_tool,
    calculator_tool,
    get_price_tool,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AgentState(TypedDict, total=False):
    """
    LangGraph 전체에서 공유할 상태.
    """

    user_query: str

    core_plan: str          # coordinator에서 만든 high-level plan
    subtask: str            # planner가 만든 이번 턴의 구체 서브태스크
    tool_mode: str          # planner가 추천하는 모드(restaurant/review/budget/...)
    tool_trace: str         # tool-agent에서 나온 중간 reasoning + 결과 요약
    draft_answer: str       # supervisor가 만든 초안
    final_answer: str       # evaluator 통과한 최종 답변

    eval_feedback: str      # evaluator의 피드백
    needs_revision: bool    # evaluator가 재수정 필요 여부
    loop_count: int         # 몇 번째 루프인지

    history: List[Dict[str, str]]  # 선택사항: 전체 에이전트 로그


llm = get_llm()


def _append_history(state: AgentState, role: str, content: str) -> None:
    history = state.get("history") or []
    history.append({"role": role, "content": content})
    state["history"] = history


# ---------------- Core Agent (coordinator) ----------------


def coordinator_node(state: AgentState) -> AgentState:
    """
    사용자의 질문과 이전 평가 피드백을 참고해서
    high-level plan(core_plan)을 작성.
    """
    user_query = state["user_query"]
    prev_feedback = state.get("eval_feedback", "")
    loop = state.get("loop_count", 0)

    system_prompt = apply_prompt_template("coordinator")
    instruct = (
        "너는 코어 플래너(coordinator)야.\n"
        "사용자의 질문을 읽고, 이번 턴에 어떤 흐름으로 문제를 해결할지 "
        "high-level 계획을 한국어로 작성해줘.\n"
        "이전 평가 단계에서 받은 피드백이 있다면 그 부분을 보완하는 방향으로 계획을 세워.\n"
        "계획만 작성하고, 답변을 완성하지는 마."
    )

    content = f"[사용자 질문]\n{user_query}\n\n"
    if loop > 0 and prev_feedback:
        content += f"[이전 평가 피드백]\n{prev_feedback}\n"

    messages = [
        SystemMessage(content=system_prompt + "\n\n" + instruct),
        HumanMessage(content=content),
    ]

    resp = llm.invoke(messages)
    plan = resp.content.strip()

    state["core_plan"] = plan
    _append_history(state, "coordinator", plan)
    logger.info("[Coordinator] plan: %s", plan[:200])
    return state


# ---------------- Planner ----------------


def planner_node(state: AgentState) -> AgentState:
    """
    core_plan + user_query를 보고,
    - 이번 턴에서 사용할 주요 subtask
    - 어떤 종류의 툴/모드에 집중할지(tool_mode)
    를 JSON 형태로 결정.
    """
    user_query = state["user_query"]
    core_plan = state.get("core_plan", "")

    system_prompt = apply_prompt_template("planner")
    instruct = (
        "너는 세부 플래너야.\n"
        "코어 계획과 사용자 질문을 보고, 이번 턴에서 수행할 구체적인 서브태스크와\n"
        "어떤 종류의 툴에 집중할지 모드를 정해.\n\n"
        "가능한 tool_mode 예시:\n"
        "- restaurant : 맛집/장소 추천 위주 (ES + Google Places)\n"
        "- review     : 리뷰/후기 요약 위주 (ES 중심)\n"
        "- budget     : 예산/비용 계산 위주 (CSV + calculator)\n"
        "- mixed      : 여러 툴이 섞일 수 있는 일반 모드\n\n"
        "아래 JSON 형식으로만 답해:\n"
        "{\n"
        '  \"tool_mode\": \"restaurant|review|budget|mixed\",\n'
        '  \"subtask\": \"...이번 턴에서 수행할 한국어 서브태스크 설명...\"\n'
        "}"
    )

    messages = [
        SystemMessage(content=system_prompt + "\n\n" + instruct),
        HumanMessage(
            content=(
                f"[사용자 질문]\n{user_query}\n\n"
                f"[코어 계획]\n{core_plan}"
            )
        ),
    ]

    resp = llm.invoke(messages)
    raw = resp.content
    logger.info("[Planner] raw: %s", raw)

    tool_mode = "mixed"
    subtask = ""
    try:
        data = json.loads(raw)
        tool_mode = data.get("tool_mode", tool_mode)
        subtask = data.get("subtask", "")
    except Exception:
        # JSON 파싱 실패 시 fallback
        subtask = raw

    state["tool_mode"] = tool_mode
    state["subtask"] = subtask
    _append_history(state, "planner", f"tool_mode={tool_mode}\nsubtask={subtask}")
    return state


# ---------------- Tool Agent (ReAct) ----------------

# ReAct 에이전트 생성 (LLM + tools)
tool_llm = get_llm()
tools = [es_search_tool, google_places_tool, calculator_tool, get_price_tool]
tool_react_agent = create_react_agent(tool_llm, tools)


def tool_agent_node(state: AgentState) -> AgentState:
    """
    ReAct 스타일로 LLM이 어떤 툴을 쓸지 스스로 선택/조합하는 노드.
    - 입력: user_query, core_plan, subtask, tool_mode
    - 출력: tool_trace (툴 실행 + reasoning + 중간 요약)
    """
    user_query = state["user_query"]
    core_plan = state.get("core_plan", "")
    subtask = state.get("subtask", "")
    tool_mode = state.get("tool_mode", "mixed")

    # tool-agent용 system/사용자 메시지 구성
    system_prompt = (
        "너는 여러 도구를 사용할 수 있는 에이전트야.\n"
        "주어진 서브태스크를 해결하기 위해 필요하다면 아래 툴들을 적절히 조합해 사용해.\n"
        f"이번 턴의 모드(tool_mode)는 '{tool_mode}'야. 이 모드의 목적에 맞게 툴을 우선 활용해.\n"
        "최종적으로는 서브태스크를 해결하는데 필요한 사실/수치/후보 리스트를 정리된 형태로 남겨줘.\n"
        "단, 사용자에게 직접 말하는 답안이 아니라, 후속 에이전트가 참고할 수 있는 메모를 작성한다고 생각해.\n"
        "- 예산/비용을 계산해야 할 때는 다음 절차를 따른다:\n"
        " 1) 먼저 menu_price_tool을 호출해 해당 식당의 메뉴 이름과 가격을 확인한다.\n"
        " 2) 사용자와 동행자의 선호(예: 김치 없음, 매운 음식, 디저트 추가 등)를 반영해 어떤 메뉴를 몇 개 주문할지 스스로 결정한다.\n"
        " 3) 결정된 메뉴 조합을 바탕으로 "12000*2 + 9000"과 같이 수식 문자열을 만들고, calculator_tool을 호출해 총 예산을 계산한다.\n"
        " 4) 최종적으로 계산된 예산 값과 선택한 메뉴들을 메모에 정리해 남긴다."
    )

    content = (
        f"[사용자 질문]\n{user_query}\n\n"
        f"[코어 계획]\n{core_plan}\n\n"
        f"[이번 턴 서브태스크]\n{subtask}\n"
    )

    # ReAct 에이전트 호출
    result = tool_react_agent.invoke(
        {
            "messages": [
                ("system", system_prompt),
                ("user", content),
            ]
        }
    )

    # 마지막 assistant 메시지를 tool_trace로 저장
    final_msg = result["messages"][-1]
    trace = final_msg.content

    state["tool_trace"] = trace
    _append_history(state, "tool_agent", trace)
    logger.info("[ToolAgent] trace: %s", trace[:300])
    return state


# ---------------- Supervisor ----------------


def supervisor_node(state: AgentState) -> AgentState:
    """
    tool_agent의 결과(tool_trace)와 plan/subtask를 참고해서
    사용자에게 보여줄 draft_answer(초안)를 생성.
    """
    user_query = state["user_query"]
    core_plan = state.get("core_plan", "")
    subtask = state.get("subtask", "")
    tool_mode = state.get("tool_mode", "mixed")
    tool_trace = state.get("tool_trace", "")

    system_prompt = apply_prompt_template("supervisor")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                "다음 정보를 바탕으로 사용자에게 보여줄 답변 초안을 작성해줘.\n\n"
                f"[사용자 질문]\n{user_query}\n\n"
                f"[코어 계획]\n{core_plan}\n\n"
                f"[이번 턴 서브태스크]\n{subtask}\n\n"
                f"[툴 실행 결과/메모]\n{tool_trace}\n\n"
                "사용자 입장에서 이해하기 쉽도록, 단계적으로 설명해줘."
            )
        ),
    ]

    resp = llm.invoke(messages)
    draft = resp.content

    state["draft_answer"] = draft
    _append_history(state, "supervisor", draft)
    return state


# ---------------- Evaluator ----------------


def evaluator_node(state: AgentState) -> AgentState:
    """
    draft_answer를 평가해서:
    - 충분하면 final_answer로 확정
    - 부족하면 feedback을 남기고 needs_revision=True 로 설정
    """
    user_query = state["user_query"]
    draft = state.get("draft_answer", "")

    system_prompt = apply_prompt_template("evaluator")
    instruct = (
        "너는 답변 평가자야.\n"
        "아래 질문과 초안 답변을 보고, 답변이 충분히 만족스러운지 평가해.\n"
        "JSON 형식으로만 답해:\n"
        "{\n"
        '  \"needs_revision\": true/false,\n'
        '  \"feedback\": \"...부족한 부분이나 개선 방향...\"\n'
        "}"
    )

    messages = [
        SystemMessage(content=system_prompt + "\n\n" + instruct),
        HumanMessage(
            content=(
                f"[사용자 질문]\n{user_query}\n\n"
                f"[초안 답변]\n{draft}"
            )
        ),
    ]

    resp = llm.invoke(messages)
    raw = resp.content
    logger.info("[Evaluator] raw: %s", raw)

    needs_revision = False
    feedback = ""
    try:
        data = json.loads(raw)
        needs_revision = bool(data.get("needs_revision", False))
        feedback = data.get("feedback", "")
    except Exception:
        # 파싱 실패 시, 그냥 이 답변을 최종으로 사용
        needs_revision = False
        feedback = "파싱 실패로 인해 현재 답변을 그대로 사용합니다."

    # loop_count 업데이트
    loop = state.get("loop_count", 0) + 1
    state["loop_count"] = loop

    # 너무 많이 루프 돌면 강제로 종료
    if loop >= 2:
        needs_revision = False

    state["needs_revision"] = needs_revision
    state["eval_feedback"] = feedback

    if not needs_revision:
        # 최종 답변 확정
        state["final_answer"] = draft

    _append_history(
        state,
        "evaluator",
        f"needs_revision={needs_revision}\nfeedback={feedback}",
    )
    return state
