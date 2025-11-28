# tools/llm_tools.py

from __future__ import annotations
import os
from typing import List, Dict, Any
from langchain_core.tools import tool

from .es_search import (
    search_es,              # BM25 ES 검색
    dense_search,           # 🔥 bge-m3 Dense Search
    search_es_csv_bm25      # CSV 테스트용 BM25 (임시)
)

from .google_place import (
    search_place,
    search_place_by_location,
    get_place_reviews_by_name_and_location,
    get_place_details
)

from .utility_func import (
    calculator,
    load_menus_for_restaurant,
)


##############################################
# 1) 하이브리드 검색 툴 (최종 검색)
##############################################
@tool
def hybrid_search_tool(query: str, size: int = 5) -> str:
    """
    ES BM25 + Dense(bge-m3) 하이브리드 검색
    
    1) BM25 (ES)
    2) Dense Search (bge-m3 임베딩)
    3) 점수 normalize 후 합산 → 상위 N개
    
    LLM이 가장 많이 사용할 근본 검색 툴.
    """

    try:
        # 🔥 1) Sparse Search (BM25)
        sparse_results = search_es(query, size=size)

        # 🔥 2) Dense Search (bge-m3)
        dense_results = dense_search(query, size=size)

        # 🔥 3) ID 기준으로 merge + 점수 normalize
        combined = {}
        
        # sparse 결과 반영
        for r in sparse_results:
            combined[r["id"]] = {
                "source": r["source"],
                "sparse_score": r["score"],
                "dense_score": 0.0,
            }
        
        # dense 결과 반영
        for r in dense_results:
            if r["id"] not in combined:
                combined[r["id"]] = {
                    "source": r["source"],
                    "sparse_score": 0.0,
                    "dense_score": r["score"],
                }
            else:
                combined[r["id"]]["dense_score"] = r["score"]

        # normalize
        sparse_max = max([c["sparse_score"] for c in combined.values()] + [1])
        dense_max = max([c["dense_score"] for c in combined.values()] + [1])

        for c in combined.values():
            c["hybrid_score"] = (
                (c["sparse_score"] / sparse_max) * 0.5 +
                (c["dense_score"] / dense_max) * 0.5
            )

        # 상위 N개 정렬
        ranked = sorted(combined.items(), key=lambda x: x[1]["hybrid_score"], reverse=True)[:size]

        # 출력 형태 변환
        lines = ["[하이브리드 검색 결과]"]
        for i, (doc_id, info) in enumerate(ranked, start=1):
            src = info["source"]
            lines.append(
                f"[{i}] {src.get('name', '이름 없음')} ({src.get('area', '')}, {src.get('category','')})\n"
                f"- 주소: {src.get('address','')}\n"
                f"- 평점: {src.get('rating','N/A')} ({src.get('user_ratings_total','?')} 리뷰)\n"
                f"- 리뷰 요약: {src.get('review_snippet','')}\n"
                f"- Hybrid Score = {info['hybrid_score']:.4f}"
            )

        return "\n\n".join(lines)

    except Exception as e:
        return f"[오류] Hybrid 검색 실패: {str(e)}"



##############################################
# 2) 기존 ES 검색 툴 (현재는 CSV 기반)
##############################################
@tool
def es_search_tool(query: str, size: int = 5) -> str:
    """
    (임시) CSV + BM25 기반 맛집 검색
    실제 서비스에서는 hybrid_search_tool을 사용하세요.
    """
    docs = search_es_csv_bm25(query=query, size=size)

    if not docs:
        return "검색 결과가 없습니다."

    lines = ["[BM25 CSV 검색 결과]"]
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



##############################################
# 3) Google API 툴 (기존 그대로 유지)
##############################################
@tool
def google_places_tool(query: str) -> str:
    ...
    # (너가 준 코드 그대로 유지 – 생략)
    ...


@tool
def google_places_by_location_tool(latitude: float, longitude: float, restaurant_name: str = "") -> str:
    ...
    # (너가 준 코드 그대로 유지 – 생략)
    ...


##############################################
# 4) 계산기 툴
##############################################
@tool
def calculator_tool(expression: str) -> str:
    try:
        value = calculator(expression)
        return f"{expression} = {value}"
    except Exception as e:
        return f"수식을 계산할 수 없습니다: {e}"


##############################################
# 5) 메뉴 조회
##############################################
@tool
def menu_price_tool(restaurant_name: str) -> str:
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
