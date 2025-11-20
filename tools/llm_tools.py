# tools/llm_tools.py

from __future__ import annotations
import os
from typing import List, Dict, Any
from langchain_core.tools import tool

from .es_search import search_es, search_es_csv_bm25
from .google_place import search_place
from .utility_func import (
    calculator,
    load_menus_for_restaurant,
)


@tool
def es_search_tool(query: str, size: int = 5) -> str:
    # """
    # ElasticSearch에서 query로 문서를 검색하고,
    # 상위 결과를 간단히 요약한 문자열로 반환한다.
    # """
    # index = os.getenv("ES_INDEX", "restaurant_docs")
    # docs = search_es(query=query, index=index, size=5)

    # if not docs:
    #     return "검색 결과가 없습니다."

    # lines = []
    # for i, d in enumerate(docs, start=1):
    #     src = d.get("source", {})
    #     title = src.get("title") or src.get("name") or f"문서 {i}"
    #     content = src.get("content") or src.get("body") or ""
    #     lines.append(f"[ES {i}] {title}: {content[:200]}")
    # return "\n".join(lines)

    """
    (테스트용) CSV + BM25 기반 맛집 검색.
    restaurants_mock.csv에서 사용자 질의와 가장 유사한 식당 상위 N개를 찾아
    LLM이 이해하기 쉬운 텍스트 형태로 반환한다.
    """
    docs = search_es_csv_bm25(query=query, size=size)

    if not docs:
        return "검색 결과가 없습니다."

    lines = ["[맛집 검색 결과]"]
    for i, d in enumerate(docs, start=1):
        src = d.get("source", {})
        name = src.get("name") or "이름 없음"
        area = src.get("area") or ""
        category = src.get("category") or ""
        address = src.get("address") or ""
        rating = src.get("rating") or "N/A"
        reviews = src.get("user_ratings_total") or "0"
        lat = src.get("latitude") or "?"
        lon = src.get("longitude") or "?"
        snippet = src.get("review_snippet") or ""

        lines.append(
            f"[{i}] {name} ({area}, {category})\n"
            f"- 주소: {address}\n"
            f"- 평점: {rating}점 ({reviews}개 리뷰)\n"
            f"- 좌표: ({lat}, {lon})\n"
            f"- 한 줄 리뷰: {snippet}"
        )

    return "\n\n".join(lines)


@tool
def google_places_tool(query: str) -> str:
    """
    Google Places API로 query와 관련된 장소를 검색하고,
    상위 후보들을 요약 문자열로 반환한다.
    """
    places = search_place(
        query=query,
        region=os.getenv("GOOGLE_PLACES_REGION", "kr"),
        limit=5,
    )
    if not places:
        return "장소 검색 결과가 없습니다."

    lines = []
    for i, p in enumerate(places, start=1):
        lines.append(
            f"[PLACE {i}] {p.get('name')} / {p.get('address')} "
            f"/ rating={p.get('rating')} / reviews={p.get('user_ratings_total')}"
        )
    return "\n".join(lines)


@tool
def calculator_tool(expression: str) -> str:
    """
    문자열 수식을 계산하는 계산기 툴.
    예: "12000 * 2 + 9000"
    """
    try:
        value = calculator(expression)
        return f"{expression} = {value}"
    except Exception as e:
        return f"수식을 계산할 수 없습니다: {e}"


@tool
def menu_price_tool(restaurant_name: str) -> str:
    """
    특정 식당(restaurant_name)의 메뉴와 가격 목록을 반환한다.
    LLM은 이 정보를 보고 어떤 메뉴를 몇 개 시킬지 결정한 뒤,
    calculator_tool을 이용해 예산을 계산할 수 있다.
    """
    csv_path = os.getenv("MENU_CSV_PATH", "data/restaurant_menus_mock.csv")

    rows = load_menus_for_restaurant(restaurant_name=restaurant_name, csv_path=csv_path)
    if not rows:
        return f"'{restaurant_name}'에 대한 메뉴 정보를 찾을 수 없습니다."

    lines = ["[메뉴 목록]"]
    for r in rows:
        menu_name = r.get("menu_name")
        menu_type = r.get("menu_type")
        price = r.get("price")
        is_rec = r.get("is_recommended", "").upper() == "Y"
        rec_flag = " (추천)" if is_rec else ""
        lines.append(f"- {menu_name} ({menu_type}, {price}원){rec_flag}")

    return "\n".join(lines)