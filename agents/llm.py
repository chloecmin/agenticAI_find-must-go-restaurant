# agents/llm.py

import os
from typing import Optional
from langchain_openai import ChatOpenAI


def get_llm(
    model_name: str = "gpt-4o-mini",
    temperature: float = 0.2,
    timeout: Optional[float] = 60.0,
):
    """
    OpenAI ChatCompletion 기반 LLM 생성 함수.

    - OPENAI_API_KEY 환경변수가 필요하다.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    llm = ChatOpenAI(
        model=model_name,
        temperature=temperature,
        timeout=timeout,
    )
    return llm
