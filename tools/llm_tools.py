# tools/llm_tools.py

from __future__ import annotations
import os
from typing import List, Dict, Any
from langchain_core.tools import tool

from .es_search import search_es, search_es_csv_bm25
from .google_place import search_place, search_place_by_location, get_place_reviews_by_name_and_location, get_place_details
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
    Google Places API로 특정 식당 이름(query)을 검색하고, 상세 정보와 리뷰를 가져온다.
    
    이 tool은 사용자가 특정 식당 이름을 직접 언급한 경우에 사용합니다.
    예: "홍대 텐동야 리뷰가 어때?" → google_places_tool("홍대 텐동야")
    
    일반적인 맛집 검색(예: "홍대 맛집 추천")의 경우에는 es_search_tool을 먼저 사용하세요.
    """
    places = search_place(
        query=query,
        region=os.getenv("GOOGLE_PLACES_REGION", "kr"),
        limit=1,  # 특정 식당이므로 첫 번째 결과만 사용
    )
    if not places:
        return f"'{query}'에 대한 검색 결과가 없습니다."

    # 첫 번째 결과 사용
    place = places[0]
    place_id = place.get("place_id")
    
    lines = [f"[Google Places 검색 결과] {place.get('name', query)}"]
    lines.append(f"- 주소: {place.get('address', '주소 정보 없음')}")
    lines.append(f"- 평점: {place.get('rating', 'N/A')}점 (전체 리뷰 {place.get('user_ratings_total', 0)}개)")
    
    # place_id가 있으면 상세 정보와 리뷰 가져오기
    if place_id:
        try:
            details = get_place_details(place_id, language="ko")
            reviews = details.get("reviews", [])
            phone_number = details.get("phone_number")
            opening_hours = details.get("opening_hours", [])
            
            # 전화번호
            if phone_number:
                lines.append(f"- 전화번호: {phone_number}")
            
            # 영업시간
            if opening_hours:
                lines.append(f"\n[영업시간]")
                for hours in opening_hours:
                    lines.append(f"  {hours}")
            
            # 리뷰 (상위 3개)
            if reviews:
                lines.append(f"\n[리뷰 요약] (상위 {len(reviews)}개):")
                for i, review in enumerate(reviews, start=1):
                    author_name = review.get("author_name", "익명")
                    rating = review.get("rating", "N/A")
                    text = review.get("text", "")
                    # 리뷰 텍스트가 너무 길면 200자로 제한
                    if len(text) > 200:
                        text = text[:200] + "..."
                    
                    lines.append(
                        f"\n{i}. {author_name} ({rating}점):\n   {text}"
                    )
            else:
                lines.append("\n[리뷰] 리뷰 정보를 가져오지 못했습니다.")
        except Exception as e:
            lines.append(f"\n[오류] 상세 정보를 가져오는 중 오류 발생: {str(e)}")
    else:
        lines.append("\n[오류] place_id가 없어 상세 정보를 가져올 수 없습니다.")
    
    return "\n".join(lines)


@tool
def google_places_by_location_tool(latitude: float, longitude: float, restaurant_name: str = "") -> str:
    """
    위도/경도와 식당 이름을 사용해서 Google Places API에서 상세 정보와 리뷰를 가져온다.
    
    이 tool은 es_search_tool에서 찾은 식당의 위도/경도와 이름을 사용해야 합니다.
    리뷰 상위 5개를 가져와서 요약합니다 (Google Places API 제한).
    
    Args:
        latitude: 위도 (예: 37.5562)
        longitude: 경도 (예: 126.9238)
        restaurant_name: 식당 이름 (필수, es_search_tool 결과에서 가져온 이름)
    """
    if not restaurant_name:
        return f"식당 이름이 필요합니다. 위도 {latitude}, 경도 {longitude}만으로는 리뷰를 가져올 수 없습니다."
    
    try:
        place_info = get_place_reviews_by_name_and_location(
            restaurant_name=restaurant_name,
            latitude=latitude,
            longitude=longitude,
            language="ko",
        )
        
        name = place_info.get("name", restaurant_name)
        address = place_info.get("address", "주소 정보 없음")
        rating = place_info.get("rating", "N/A")
        user_ratings_total = place_info.get("user_ratings_total", 0)
        reviews = place_info.get("reviews", [])
        phone_number = place_info.get("phone_number")
        opening_hours = place_info.get("opening_hours", [])
        
        lines = [f"[Google Places 상세 정보] {name}"]
        lines.append(f"- 주소: {address}")
        lines.append(f"- 평점: {rating}점 (전체 리뷰 {user_ratings_total}개)")
        
        # 전화번호
        if phone_number:
            lines.append(f"- 전화번호: {phone_number}")
        
        # 영업시간
        if opening_hours:
            lines.append(f"\n[영업시간]")
            for hours in opening_hours:
                lines.append(f"  {hours}")
        
        # 리뷰 (상위 3개)
        if reviews:
            lines.append(f"\n[리뷰 요약] (상위 {len(reviews)}개):")
            for i, review in enumerate(reviews, start=1):
                author_name = review.get("author_name", "익명")
                rating = review.get("rating", "N/A")
                text = review.get("text", "")
                # 리뷰 텍스트가 너무 길면 200자로 제한
                if len(text) > 200:
                    text = text[:200] + "..."
                
                lines.append(
                    f"\n{i}. {author_name} ({rating}점):\n   {text}"
                )
        else:
            lines.append("\n[리뷰] 리뷰 정보를 가져오지 못했습니다.")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Google Places API 호출 중 오류 발생: {str(e)}"


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