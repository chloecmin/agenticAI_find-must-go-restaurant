import os
import json
import logging
import re
from typing import TypedDict, List, Dict, Any

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from agents.llm import get_llm
from prompts.template import apply_prompt_template
from tools.llm_tools import (
    es_search_tool,
    google_places_tool,
    google_places_by_location_tool,
    calculator_tool,
    menu_price_tool,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 로그 포맷 설정 (터미널에서 더 잘 보이도록)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


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

    # 세션 단위 Short-term Memory
    # 같은 thread_id 에서 다음 질문이 들어왔을 때 참고할 정보들
    session_memory: Dict[str, Any]   # 직전 질의/답변 등 세션 전반 요약
    # user_profile: Dict[str, Any]     # 맛집 취향 (지역, 예산, 선호/비선호 등) 구현 못함
    # last_reco: List[Dict[str, Any]]  # 직전 턴 추천 리스트 (중복 회피용) 구현 못함


# 기본 LLM (coordinator, planner, supervisor, evaluator용)
# 환경변수 BASE_LLM_MODEL로 설정 가능 (기본값: qwen/qwen3-30b-a3b:free)
llm = get_llm(model_name=os.getenv("BASE_LLM_MODEL", "qwen/qwen3-30b-a3b:free"))


def _append_history(state: AgentState, role: str, content: str) -> None:
    history = state.get("history") or []
    history.append({"role": role, "content": content})
    state["history"] = history


def update_session_memory(state: AgentState) -> None:
    """
    한 턴이 끝났을 때 세션 단위 메모리/프로필/직전 추천을 업데이트한다.
    - session_memory: 직전 질의/답변/툴트레이스 요약
    - user_profile: 쿼리에서 지역 등 간단한 취향/제약 추출 (구현 못함)
    - last_reco: tool_trace에서 식당 목록만 뽑아 저장 (구현 못함)
    """
    session = state.get("session_memory") or {}
    # profile = state.get("user_profile") or {} 구현 못함

    user_query = state.get("user_query", "")
    final_answer = state.get("final_answer", "")
    tool_trace = state.get("tool_trace", "")

    # 직전 턴 요약 정보
    session["last_user_query"] = user_query
    session["last_final_answer"] = final_answer[-3000:]
    session["last_tool_trace"] = tool_trace[-3000:]

    state["session_memory"] = session



# ---------------- Core Agent (coordinator) ----------------


def coordinator_node(state: AgentState) -> AgentState:
    """
    사용자의 질문과 이전 평가 피드백을 참고해서
    high-level plan(core_plan)을 작성.
    """
    user_query = state["user_query"]
    prev_feedback = state.get("eval_feedback", "")
    loop = state.get("loop_count", 0)
    session_memory = state.get("session_memory", {})
    user_profile = state.get("user_profile", {})

    # 디버깅용
    print("\n[DEBUG][coordinator] session_memory:", session_memory)

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

    try:
        resp = llm.invoke(messages)
        plan = resp.content.strip()
    except Exception as e:
        # LLM 에러를 잡아준다.
        logger.error("[Coordinator] LLM 호출 실패, fallback plan 사용: %s", e)

        # fallback: 그냥 사용자 질문 + 이전 피드백/메모리를 planner에게 넘기는 단순 계획
        plan = (
            "LLM 호출 실패로 인해 단순 플랜을 사용합니다.\n\n"
            f"- 사용자 질문을 그대로 planner에게 전달합니다.\n"
            f"- 이전 평가 피드백과 세션 메모리가 있다면 planner가 참고하도록 합니다.\n\n"
            f"[사용자 질문]\n{user_query}\n"
        )

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

    system_prompt = apply_prompt_template("planner", {"USER_REQUEST": user_query})
    instruct = (
        "너는 세부 플래너야.\n"
        "코어 계획과 사용자 질문을 보고, 이번 턴에서 수행할 구체적인 서브태스크와\n"
        "어떤 종류의 툴에 집중할지 모드를 정해.\n\n"
        "가능한 tool_mode 값 (반드시 이 중 하나만 사용):\n"
        "- restaurant : 맛집/장소 추천 위주\n"
        "- review     : 리뷰/후기 요약 위주\n"
        "- budget     : 예산/비용 계산 위주\n"
        "- mixed      : 여러 툴이 섞일 수 있는 일반 모드\n\n"
        "중요: 반드시 아래 JSON 형식으로만 답변하세요. 다른 텍스트는 포함하지 마세요.\n"
        "JSON 형식:\n"
        '{"tool_mode": "restaurant", "subtask": "구체적인 서브태스크 설명"}\n\n'
        "예시:\n"
        '{"tool_mode": "restaurant", "subtask": "홍대 지역의 맛집을 검색하여 추천 목록 작성"}'
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
    logger.info("[Planner] raw response (full): %s", raw)
    logger.info("[Planner] raw response length: %d", len(raw))

    tool_mode = "mixed"
    subtask = ""
    
    # 방법 1: 정규식으로 직접 추출 (가장 안전)
    mode_match = re.search(r'"tool_mode"\s*:\s*["\']([^"\']+)["\']', raw, re.IGNORECASE)
    if mode_match:
        tool_mode = mode_match.group(1).strip().lower()
        logger.info("[Planner] tool_mode found via regex: %s", tool_mode)
    
    # subtask는 여러 줄일 수 있으므로 더 넓은 패턴 사용
    subtask_match = re.search(r'"subtask"\s*:\s*["\']((?:[^"\'\\]|\\.)+)["\']', raw, re.IGNORECASE | re.DOTALL)
    if not subtask_match:
        # 따옴표 없이도 찾기
        subtask_match = re.search(r'"subtask"\s*:\s*([^,}\n]+)', raw, re.IGNORECASE)
    if subtask_match:
        subtask = subtask_match.group(1).strip().strip('"').strip("'")
        logger.info("[Planner] subtask found via regex: %s", subtask[:100])
    
    # 방법 2: 정규식으로 찾지 못한 경우 JSON 파싱 시도
    if tool_mode == "mixed" or not subtask:
        try:
            # JSON 블록 추출
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
            if code_block_match:
                json_str = code_block_match.group(1)
            else:
                # 일반 JSON 객체 추출
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = raw
            
            # JSON 문자열 정리 (모든 줄바꿈과 불필요한 공백 제거)
            json_str = json_str.strip()
            # 키 이름의 줄바꿈 제거
            json_str = re.sub(r'"\s*\n\s*"', '", "', json_str)
            json_str = re.sub(r':\s*\n\s*', ': ', json_str)
            
            logger.info("[Planner] cleaned json_str: %s", json_str[:300])
            
            # JSON 파싱
            data = json.loads(json_str)
            logger.info("[Planner] parsed data keys: %s", list(data.keys()) if isinstance(data, dict) else "not a dict")
            
            # 안전하게 키 접근
            if isinstance(data, dict):
                # 원본 키로 먼저 시도
                if "tool_mode" in data:
                    tool_mode = str(data["tool_mode"]).strip().lower()
                elif "toolMode" in data:
                    tool_mode = str(data["toolMode"]).strip().lower()
                
                if "subtask" in data:
                    subtask = str(data["subtask"]).strip()
                elif "subTask" in data:
                    subtask = str(data["subTask"]).strip()
                
                # 위에서 못 찾은 경우 모든 키를 순회
                if tool_mode == "mixed" or not subtask:
                    for key, value in data.items():
                        key_str = str(key).strip().lower().replace('\n', '').replace('"', '').replace(' ', '')
                        if 'toolmode' in key_str or 'tool_mode' in key_str:
                            tool_mode = str(value).strip().lower()
                        elif 'subtask' in key_str:
                            subtask = str(value).strip()
            
        except json.JSONDecodeError as e:
            logger.warning(f"[Planner] JSON 파싱 실패: {e}, json_str: {json_str[:200] if 'json_str' in locals() else 'N/A'}")
        except KeyError as e:
            logger.warning(f"[Planner] KeyError 발생: {e}, data keys: {list(data.keys()) if 'data' in locals() and isinstance(data, dict) else 'N/A'}")
        except Exception as e:
            logger.warning(f"[Planner] 예상치 못한 에러: {e}, type: {type(e)}")
    
    # tool_mode 값 정리
    if tool_mode and tool_mode != "mixed":
        tool_mode = str(tool_mode).strip().lower()
        # "tool_mode-restaurant" 같은 형식에서 "restaurant" 추출
        if "-" in tool_mode:
            tool_mode = tool_mode.split("-")[-1]
        # 유효한 tool_mode인지 확인
        valid_modes = ["restaurant", "review", "budget", "mixed"]
        if tool_mode not in valid_modes:
            logger.warning(f"[Planner] 유효하지 않은 tool_mode: {tool_mode}, 기본값 'mixed' 사용")
            tool_mode = "mixed"
    
    # subtask가 없으면 raw 전체를 사용
    if not subtask:
        subtask = raw.strip()
        logger.warning("[Planner] subtask를 찾지 못해 raw 전체 사용")
    
    logger.info("[Planner] 최종 결과 - tool_mode: %s, subtask: %s", tool_mode, subtask[:100])

    state["tool_mode"] = tool_mode
    state["subtask"] = subtask
    _append_history(state, "planner", f"tool_mode={tool_mode}\nsubtask={subtask}")
    return state


# ---------------- Sub Agents (ReAct) ----------------

# Sub Agent용 LLM (tool use를 지원하는 모델 필요)
sub_agent_llm = get_llm(model_name=os.getenv("TOOL_LLM_MODEL", "openai/gpt-4o-mini"))


# ---------------- Search Agent ----------------

search_agent = create_react_agent(sub_agent_llm, [es_search_tool])


def search_agent_node(state: AgentState) -> AgentState:
    """
    맛집 검색을 담당하는 Sub Agent.
    es_search_tool을 사용해서 맛집 리스트를 찾습니다.
    """
    user_query = state["user_query"]
    core_plan = state.get("core_plan", "")
    subtask = state.get("subtask", "")
    
    system_prompt = apply_prompt_template("search_agent")
    
    content = (
        f"[사용자 질문]\n{user_query}\n\n"
        f"[코어 계획]\n{core_plan}\n\n"
        f"[이번 턴 서브태스크]\n{subtask}\n\n"
        "위 정보를 바탕으로 es_search_tool을 사용해서 맛집을 검색해줘."
    )
    
    result = search_agent.invoke({
        "messages": [
            ("system", system_prompt),
            ("user", content),
        ]
    })
    
    final_msg = result["messages"][-1]
    trace = final_msg.content
    
    # 기존 tool_trace에 추가 (여러 sub agent 결과를 합치기 위해)
    existing_trace = state.get("tool_trace", "")
    if existing_trace:
        state["tool_trace"] = existing_trace + "\n\n[Search Agent 결과]\n" + trace
    else:
        state["tool_trace"] = "[Search Agent 결과]\n" + trace
    
    _append_history(state, "search_agent", trace)
    
    # 전체 trace를 로그에 출력
    logger.info("[SearchAgent] ===== 전체 Trace 시작 (총 %d자) =====", len(trace))
    logger.info("[SearchAgent] 전체 내용:\n%s", trace)
    logger.info("[SearchAgent] ===== 전체 Trace 종료 =====")
    
    return state


# ---------------- Places Agent ----------------

places_agent = create_react_agent(sub_agent_llm, [google_places_tool, google_places_by_location_tool])


def places_agent_node(state: AgentState) -> AgentState:
    """
    Google Places 정보를 가져오는 Sub Agent.
    google_places_tool 또는 google_places_by_location_tool을 사용합니다.
    """
    user_query = state["user_query"]
    core_plan = state.get("core_plan", "")
    subtask = state.get("subtask", "")
    tool_trace = state.get("tool_trace", "")  # search_agent 결과가 있을 수 있음
    
    system_prompt = apply_prompt_template("places_agent")
    
    content = (
        f"[사용자 질문]\n{user_query}\n\n"
        f"[코어 계획]\n{core_plan}\n\n"
        f"[이번 턴 서브태스크]\n{subtask}\n\n"
    )
    
    if tool_trace:
        content += f"[이전 검색 결과 (참고용)]\n{tool_trace}\n\n"
    
    content += "위 정보를 바탕으로 Google Places에서 식당 정보와 리뷰를 가져와줘."
    
    result = places_agent.invoke({
        "messages": [
            ("system", system_prompt),
            ("user", content),
        ]
    })
    
    final_msg = result["messages"][-1]
    trace = final_msg.content
    
    # 기존 tool_trace에 추가
    existing_trace = state.get("tool_trace", "")
    if existing_trace:
        state["tool_trace"] = existing_trace + "\n\n[Places Agent 결과]\n" + trace
    else:
        state["tool_trace"] = "[Places Agent 결과]\n" + trace
    
    _append_history(state, "places_agent", trace)
    
    # 전체 trace를 로그에 출력
    logger.info("[PlacesAgent] ===== 전체 Trace 시작 (총 %d자) =====", len(trace))
    logger.info("[PlacesAgent] 전체 내용:\n%s", trace)
    logger.info("[PlacesAgent] ===== 전체 Trace 종료 =====")
    
    return state


# ---------------- Budget Agent ----------------

budget_agent = create_react_agent(sub_agent_llm, [calculator_tool, menu_price_tool])


def budget_agent_node(state: AgentState) -> AgentState:
    """
    예산 계산을 담당하는 Sub Agent.
    calculator_tool과 menu_price_tool을 사용합니다.
    """
    user_query = state["user_query"]
    core_plan = state.get("core_plan", "")
    subtask = state.get("subtask", "")
    tool_trace = state.get("tool_trace", "")  # search_agent나 places_agent 결과가 있을 수 있음
    
    system_prompt = apply_prompt_template("budget_agent")
    
    content = (
        f"[사용자 질문]\n{user_query}\n\n"
        f"[코어 계획]\n{core_plan}\n\n"
        f"[이번 턴 서브태스크]\n{subtask}\n\n"
    )
    
    if tool_trace:
        content += f"[이전 검색 결과 (참고용)]\n{tool_trace}\n\n"
    
    content += "위 정보를 바탕으로 예산을 계산해줘."
    
    result = budget_agent.invoke({
        "messages": [
            ("system", system_prompt),
            ("user", content),
        ]
    })
    
    final_msg = result["messages"][-1]
    trace = final_msg.content
    
    # 기존 tool_trace에 추가
    existing_trace = state.get("tool_trace", "")
    if existing_trace:
        state["tool_trace"] = existing_trace + "\n\n[Budget Agent 결과]\n" + trace
    else:
        state["tool_trace"] = "[Budget Agent 결과]\n" + trace
    
    _append_history(state, "budget_agent", trace)
    
    # 전체 trace를 로그에 출력
    logger.info("[BudgetAgent] ===== 전체 Trace 시작 (총 %d자) =====", len(trace))
    logger.info("[BudgetAgent] 전체 내용:\n%s", trace)
    logger.info("[BudgetAgent] ===== 전체 Trace 종료 =====")
    
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

    logger.info("[Supervisor] 시작 - tool_trace 길이: %d", len(tool_trace))
    
    system_prompt = apply_prompt_template("supervisor")
    
    # tool_trace가 너무 길면 일부만 사용 (LLM 토큰 제한 고려)
    tool_trace_preview = tool_trace[:3000] if len(tool_trace) > 3000 else tool_trace
    if len(tool_trace) > 3000:
        tool_trace_preview += "\n\n[참고: tool_trace가 길어 일부만 표시했습니다. 위 정보를 우선 참고하세요.]"
        logger.warning("[Supervisor] tool_trace가 너무 길어 일부만 사용: %d -> %d", len(tool_trace), len(tool_trace_preview))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                "다음 정보를 바탕으로 사용자에게 보여줄 답변 초안을 작성해줘.\n\n"
                f"[사용자 질문]\n{user_query}\n\n"
                f"[코어 계획]\n{core_plan}\n\n"
                f"[이번 턴 서브태스크]\n{subtask}\n\n"
                f"[툴 실행 결과/메모]\n{tool_trace_preview}\n\n"
                "**중요: es_search_tool 결과에 나온 식당만 언급해야 합니다. "
                "검색 결과에 '[1] 식당명', '[2] 식당명' 형식으로 나온 식당들만 답변에 포함하고, "
                "검색 결과에 없는 식당은 절대 언급하지 마세요. "
                "사용자 입장에서 이해하기 쉽도록, 단계적으로 설명해줘."
            )
        ),
    ]

    try:
        logger.info("[Supervisor] LLM 호출 시작...")
        resp = llm.invoke(messages)
        draft = resp.content
        logger.info("[Supervisor] LLM 응답 받음, 길이: %d", len(draft))
        logger.info("[Supervisor] draft 미리보기: %s", draft[:200])
    except Exception as e:
        logger.error("[Supervisor] LLM 호출 실패: %s", str(e))
        # 에러 발생 시 기본 답변 생성
        draft = (
            f"죄송합니다. 답변 생성 중 오류가 발생했습니다.\n\n"
            f"사용자 질문: {user_query}\n\n"
            f"툴 실행 결과에서 다음 정보를 확인했습니다:\n{tool_trace[:500]}"
        )

    state["draft_answer"] = draft
    _append_history(state, "supervisor", draft)
    logger.info("[Supervisor] 완료")
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

    try:
        resp = llm.invoke(messages)
        raw = resp.content
        logger.info("[Evaluator] raw: %s", raw)
    except Exception as e:
        # LLM 에러 발생 시 안전하게 종료
        logger.error("[Evaluator] LLM 호출 실패: %s", e)

        # loop_count 업데이트
        loop = state.get("loop_count", 0) + 1
        state["loop_count"] = loop

        # 더 이상 재수정 시도 X → 지금 draft를 최종 답변으로 사용
        state["needs_revision"] = False
        state["eval_feedback"] = f"LLM 평가 중 오류 발생: {e}"
        state["final_answer"] = draft or "죄송합니다. 현재 답변을 평가하는 데 문제가 발생했습니다."

        _append_history(
            state,
            "evaluator",
            f"[ERROR] LLM 호출 실패, draft를 그대로 최종으로 사용\nerror={e}",
        )
        return state


    needs_revision = False
    feedback = ""
    try:
        # JSON 블록 추출 시도
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1)
        else:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = raw
        
        json_str = json_str.strip()
        data = json.loads(json_str)
        
        needs_revision = bool(data.get("needs_revision", False))
        feedback = data.get("feedback", "")
        
        # feedback이 있고 개선이 필요하다고 언급되면 needs_revision을 true로 설정
        if feedback and not needs_revision:
            # feedback 내용 분석: 개선, 부족, 추가 등의 키워드가 있으면 revision 필요
            improvement_keywords = ["부족", "개선", "추가", "더", "명확", "정리", "설명", "보완", "수정"]
            if any(keyword in feedback for keyword in improvement_keywords):
                logger.info("[Evaluator] feedback에 개선 요구가 있어 needs_revision을 true로 설정")
                needs_revision = True
                
    except Exception as e:
        # 파싱 실패 시, 그냥 이 답변을 최종으로 사용
        logger.warning(f"[Evaluator] JSON 파싱 실패: {e}, raw: {raw[:200]}")
        needs_revision = False
        feedback = "파싱 실패로 인해 현재 답변을 그대로 사용합니다."

    # loop_count 업데이트
    loop = state.get("loop_count", 0) + 1
    state["loop_count"] = loop

    # 너무 많이 루프 돌면 강제로 종료 (최대 3번: 첫 실행 + 재시도 2번)
    if loop >= 3:
        needs_revision = False
        logger.info("[Evaluator] 최대 루프 횟수(3번) 도달, 강제 종료")

    state["needs_revision"] = needs_revision
    state["eval_feedback"] = feedback

    if not needs_revision:
        # 최종 답변 확정
        state["final_answer"] = draft
        logger.info("[Evaluator] 최종 답변 확정: %s", draft[:200])
    else:
        logger.info("[Evaluator] 재검토 필요, coordinator로 복귀. feedback: %s", feedback[:200])

    _append_history(
        state,
        "evaluator",
        f"needs_revision={needs_revision}\nfeedback={feedback}",
    )
    return state


# ---------------- Final Output ----------------

def final_output_node(state: AgentState) -> AgentState:
    """
    최종 답변(final_answer)을 가독성 좋게 정리하고 출력하는 노드.
    포맷팅된 답변을 state에 저장하여 LangGraph Studio에서도 확인할 수 있도록 함.
    """
    final_answer = state.get("final_answer", "")
    
    if final_answer:
        # LLM을 사용해서 가독성 좋게 정리
        system_prompt = apply_prompt_template("final_output")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    "아래 최종 답변을 가독성 좋게 정리해서 다시 작성해줘.\n\n"
                    f"[원본 답변]\n{final_answer}"
                )
            ),
        ]
        
        try:
            logger.info("[FinalOutput] 답변 포맷팅 시작...")
            resp = llm.invoke(messages)
            formatted_answer = resp.content
            
            # 포맷팅된 답변을 state에 저장 (LangGraph Studio에서 확인 가능)
            state["final_answer"] = formatted_answer

            # 세션 단위 메모리 업데이트
            update_session_memory(state)
            
            # 터미널에 출력
            print("\n" + "="*80)
            print("최종 답변")
            print("="*80)
            print(formatted_answer)
            print("="*80 + "\n")
            logger.info("[FinalOutput] 최종 답변 출력 완료 (포맷팅됨)")
        except Exception as e:
            logger.error("[FinalOutput] 포맷팅 실패: %s, 원본 출력", str(e))
            # 포맷팅 실패 시 원본 답변 유지
            print("\n" + "="*80)
            print("최종 답변")
            print("="*80)
            print(final_answer)
            print("="*80 + "\n")
    else:
        print("\n[경고] final_answer가 설정되지 않았습니다.\n")
        logger.warning("[FinalOutput] final_answer가 없습니다.")
    
    return state
