# agents/llm.py

import os
from typing import Optional
from langchain_openai import ChatOpenAI


def get_llm(
    model_name: str = "qwen/qwen3-30b-a3b:free",
    temperature: float = 0.2,
    timeout: Optional[float] = 120.0,  # 무료 모델은 느릴 수 있으므로 120초로 증가
):
    """
    OpenRouter를 통한 LLM 생성 함수.
    
    OpenRouter는 여러 LLM 모델에 접근할 수 있는 통합 API입니다.
    모델 이름 형식: "openai/gpt-4o", "anthropic/claude-3-opus", "google/gemini-pro" 등
    
    - OPENROUTER_API_KEY 환경변수가 필요하다.
    - OpenRouter 모델 목록: https://openrouter.ai/models
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")

    llm = ChatOpenAI(
        model=model_name,
        temperature=temperature,
        timeout=timeout,
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", ""),  # 선택사항: 앱 URL
            "X-Title": os.getenv("OPENROUTER_APP_NAME", "LangGraph Agent"),  # 선택사항: 앱 이름
        },
    )
    return llm
