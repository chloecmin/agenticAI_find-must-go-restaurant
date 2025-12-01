# tools/llm_tools.py

from __future__ import annotations
import os
from typing import List, Dict, Any
from langchain_core.tools import tool

from .es_search import search_es, search_es_csv_bm25, dense_search, extract_cuisine_type, translate_query_to_english
from .google_place import search_place, search_place_by_location, get_place_reviews_by_name_and_location, get_place_details
from .utility_func import (
    calculator,
    load_menus_for_restaurant,
)


@tool
def es_search_tool(query: str, size: int = 5) -> str:
    """
    ES BM25 (Sparse) + bge-m3 Dense (KNN) 하이브리드 검색
    RRF(Reciprocal Rank Fusion)로 결과 결합
    
    실제 Elasticsearch에서 맛집을 검색합니다.
    
    Args:
        query: 검색 쿼리 (예: "홍대 우동", "강남 한식")
        size: 반환할 결과 개수 (기본값: 5)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"[es_search_tool] 검색 시작: query='{query}', size={size}")
        
        # 음식 종류 추출 (한식, 일식, 중식 등) - 후처리 필터링용
        cuisine_type, _ = extract_cuisine_type(query)
        
        # 번역된 쿼리에서도 음식 종류 확인 (번역 후 영어 키워드가 나올 수 있음)
        if not cuisine_type:
            translated_query = translate_query_to_english(query)
            if translated_query != query:
                cuisine_type, _ = extract_cuisine_type(translated_query)
        
        # 1) Sparse Search (BM25) - 10개 가져오기
        sparse_results = []
        try:
            logger.info("[es_search_tool] Sparse 검색 시작...")
            sparse_results = search_es(query, size=10)
            logger.info(f"[es_search_tool] Sparse 검색 완료: {len(sparse_results)}개 결과")
        except Exception as e:
            logger.warning(f"[es_search_tool] Sparse 검색 실패 (계속 진행): {str(e)}")
        
        # 2) Dense Search (KNN) - 10개 가져오기
        dense_results = []
        try:
            logger.info("[es_search_tool] Dense 검색 시작...")
            dense_results = dense_search(query, size=10)
            logger.info(f"[es_search_tool] Dense 검색 완료: {len(dense_results)}개 결과")
        except Exception as e:
            logger.warning(f"[es_search_tool] Dense 검색 실패 (Sparse 결과만 사용): {str(e)}")
        
        # 둘 다 실패한 경우
        if not sparse_results and not dense_results:
            logger.error("[es_search_tool] Sparse와 Dense 검색 모두 실패했습니다.")
            return "검색 결과가 없습니다. Elasticsearch 연결 또는 인덱스를 확인해주세요."
        
        # 3) RRF로 결과 결합 (k=60)
        logger.info("[es_search_tool] RRF 결합 시작...")
        fused_results = _rrf_fusion(sparse_results, dense_results, k=60)
        logger.info(f"[es_search_tool] RRF 결합 완료: {len(fused_results)}개 결과")
        
        # 4) 특정 음식 종류 검색인 경우 결과 필터링 (cuisines에 해당 키워드 포함 확인)
        if cuisine_type:
            logger.info(f"[es_search_tool] {cuisine_type} 음식 검색: cuisines 필드 필터링 시작...")
            filtered_results = []
            cuisine_type_lower = cuisine_type.lower()
            
            for result in fused_results:
                source = result.get("source", {})
                cuisines = source.get("cuisines", "") or source.get("Cuisines", "") or ""
                cuisines_lower = cuisines.lower()
                
                # 해당 음식 키워드가 cuisines에 포함되어 있는지 확인
                if cuisine_type_lower in cuisines_lower:
                    filtered_results.append(result)
                    logger.info(f"[es_search_tool] ✅ {cuisine_type} 매칭: {source.get('restaurant_name', 'N/A')} (cuisines: {cuisines})")
                else:
                    logger.info(f"[es_search_tool] ❌ {cuisine_type} 아님 (제외): {source.get('restaurant_name', 'N/A')} (cuisines: {cuisines})")
            
            logger.info(f"[es_search_tool] 필터링 완료: {len(fused_results)}개 → {len(filtered_results)}개 ({cuisine_type}만)")
            fused_results = filtered_results
            
            if not fused_results:
                logger.warning(f"[es_search_tool] {cuisine_type} 음식 검색 결과가 없습니다.")
                cuisine_name = {"Korean": "한국", "Japanese": "일본", "Chinese": "중국", "Italian": "이탈리아", 
                               "Thai": "태국", "Indian": "인도", "Mexican": "멕시코", "French": "프랑스",
                               "Western": "서양", "European": "유럽"}.get(cuisine_type, cuisine_type)
                return f"검색 결과가 없습니다. {cuisine_name}음식을 제공하는 식당을 찾지 못했습니다."
        
        # 5) 상위 N개 선택
        top_results = fused_results[:size]
        
        if not top_results:
            logger.warning("[es_search_tool] 검색 결과가 없습니다.")
            return "검색 결과가 없습니다."
        
        logger.info(f"[es_search_tool] 최종 결과 {len(top_results)}개 반환")
        
        # 5) 결과 포맷팅
        lines = ["[맛집 검색 결과]"]
        for i, result in enumerate(top_results, start=1):
            source = result["source"]
            rrf_score = result["rrf_score"]
            
            # 실제 필드명에 맞춰 추출 (모두 소문자+언더스코어)
            name = source.get("restaurant_name") or source.get("Restaurant Name") or source.get("name") or "이름 없음"
            city = source.get("city") or source.get("City") or ""
            cuisines = source.get("cuisines") or source.get("Cuisines") or ""
            address = source.get("address") or source.get("Address") or ""
            locality = source.get("locality") or source.get("Locality") or ""
            locality_verbose = source.get("locality_verbose") or source.get("Locality Verbose") or ""
            rating = source.get("aggregate_rating") or source.get("Aggregate rating") or source.get("rating") or "N/A"
            votes = source.get("votes") or source.get("Votes") or "0"
            price_range = source.get("price_range") or source.get("Price range") or ""
            avg_cost = source.get("average_cost_for_two") or source.get("Average Cost for two") or ""
            currency = source.get("currency") or source.get("Currency") or ""
            latitude = source.get("latitude") or source.get("Latitude") or "?"
            longitude = source.get("longitude") or source.get("Longitude") or "?"
            
            # 지역 정보 (locality_verbose 우선, 없으면 locality)
            location_info = locality_verbose or locality
            location_str = f", {location_info}" if location_info else ""
            
            # cuisines 정보 강조 (검색 쿼리와 관련된 경우)
            cuisines_display = cuisines if cuisines else "요리 정보 없음"
            # RRF 스코어도 포함 (디버깅/신뢰도 표시용)
            
            lines.append(
                f"[{i}] {name} ({city}{location_str})\n"
                f"- 🍽️ 요리 종류: {cuisines_display}\n"
                f"- 📍 주소: {address}\n"
                f"- ⭐ 평점: {rating}점 ({votes}표)\n"
                + (f"- 💰 가격대: {price_range} ({avg_cost} {currency})" if avg_cost else "- 💰 가격 정보 없음")
                + f"\n- 🗺️ 좌표: ({latitude}, {longitude})"
                + f"\n- 📊 검색 매칭 점수: {rrf_score:.4f}"
            )
        
        result_text = "\n\n".join(lines)
        logger.info(f"[es_search_tool] 검색 완료. 결과 길이: {len(result_text)}자")
        return result_text
        
    except Exception as e:
        import traceback
        error_msg = f"[오류] 검색 실패: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"[es_search_tool] {error_msg}")
        return error_msg


##############################################
# 하이브리드 검색 툴 (BM25 + Dense + RRF)
##############################################

def _rrf_fusion(
    sparse_results: List[Dict[str, Any]],
    dense_results: List[Dict[str, Any]],
    k: int = 60
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) 알고리즘으로 검색 결과 결합
    
    Args:
        sparse_results: BM25 검색 결과
        dense_results: Dense 검색 결과
        k: RRF 상수 (기본값 60)
        
    Returns:
        RRF 점수로 정렬된 결과 리스트
    """
    # 각 문서의 RRF 점수 계산
    rrf_scores: Dict[str, Dict[str, Any]] = {}
    
    # Sparse 결과 반영
    for rank, result in enumerate(sparse_results):
        doc_id = result["id"]
        rrf_score = 1.0 / (k + rank + 1)
        
        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = {
                "id": doc_id,
                "source": result["source"],
                "rrf_score": rrf_score,
                "sparse_rank": rank + 1,
                "dense_rank": None,
            }
        else:
            rrf_scores[doc_id]["rrf_score"] += rrf_score
            rrf_scores[doc_id]["sparse_rank"] = rank + 1
    
    # Dense 결과 반영
    for rank, result in enumerate(dense_results):
        doc_id = result["id"]
        rrf_score = 1.0 / (k + rank + 1)
        
        if doc_id not in rrf_scores:
            rrf_scores[doc_id] = {
                "id": doc_id,
                "source": result["source"],
                "rrf_score": rrf_score,
                "sparse_rank": None,
                "dense_rank": rank + 1,
            }
        else:
            rrf_scores[doc_id]["rrf_score"] += rrf_score
            rrf_scores[doc_id]["dense_rank"] = rank + 1
    
    # RRF 점수 기준으로 정렬
    sorted_results = sorted(
        rrf_scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True
    )
    
    return sorted_results


@tool
def hybrid_search_tool(query: str, size: int = 5) -> str:
    """
    ES BM25 (Sparse) + bge-m3 Dense (KNN) 하이브리드 검색
    RRF(Reciprocal Rank Fusion)로 결과 결합
    
    1) BM25 Sparse 검색 (10개)
    2) Dense KNN 검색 (10개)
    3) RRF로 결과 결합 후 상위 N개 반환
    
    LLM이 가장 많이 사용할 근본 검색 툴.
    """
    try:
        # 1) Sparse Search (BM25) - 10개 가져오기
        sparse_results = search_es(query, size=10)
        
        # 2) Dense Search (KNN) - 10개 가져오기
        dense_results = dense_search(query, size=10)
        
        # 3) RRF로 결과 결합 (k=60)
        fused_results = _rrf_fusion(sparse_results, dense_results, k=60)
        
        # 4) 상위 N개 선택
        top_results = fused_results[:size]
        
        if not top_results:
            return "검색 결과가 없습니다."
        
        # 5) 결과 포맷팅
        lines = ["[하이브리드 검색 결과 (BM25 + Dense + RRF)]"]
        for i, result in enumerate(top_results, start=1):
            source = result["source"]
            doc_id = result["id"]
            rrf_score = result["rrf_score"]
            
            # 실제 필드명에 맞춰 추출
            name = source.get("Restaurant Name") or source.get("name") or "이름 없음"
            city = source.get("City") or source.get("city") or ""
            cuisines = source.get("Cuisines") or source.get("cuisines") or ""
            address = source.get("Address") or source.get("address") or ""
            locality = source.get("Locality") or source.get("locality") or ""
            rating = source.get("Aggregate rating") or source.get("rating") or "N/A"
            votes = source.get("Votes") or source.get("votes") or "0"
            price_range = source.get("Price range") or source.get("price_range") or ""
            avg_cost = source.get("Average Cost for two") or source.get("average_cost") or ""
            currency = source.get("Currency") or source.get("currency") or ""
            
            lines.append(
                f"[{i}] {name}\n"
                f"- 위치: {city}" + (f", {locality}" if locality else "") + "\n"
                f"- 요리: {cuisines}\n"
                f"- 주소: {address}\n"
                f"- 평점: {rating}점 ({votes}표)\n"
                + (f"- 가격대: {price_range} ({avg_cost} {currency})" if avg_cost else "- 가격 정보 없음")
                + f"\n- RRF Score: {rrf_score:.6f}"
                + (f" (Sparse: {result['sparse_rank']}, Dense: {result['dense_rank']})" 
                   if result['sparse_rank'] and result['dense_rank'] 
                   else f" (Sparse: {result['sparse_rank'] or 'N/A'}, Dense: {result['dense_rank'] or 'N/A'})")
            )
        
        return "\n\n".join(lines)
        
    except Exception as e:
        return f"[오류] Hybrid 검색 실패: {str(e)}"


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
    csv_path = os.getenv("MENU_CSV_PATH", "data/restaurants_menus_mock.csv")

    rows = load_menus_for_restaurant(restaurant_name=restaurant_name, csv_path=csv_path)
    if not rows:
        return f"'{restaurant_name}'에 대한 메뉴 정보를 찾을 수 없습니다."

    lines = ["[메뉴 목록]"]
    for r in rows:
        menu_name = r.get("menu_name")
        menu_type = r.get("menu_type")
        price = r.get("price")

        # -- is_recommended 처리 (0/1, "0"/"1", "Y"/"N", True/False 모두 대응) --
        value = r.get("is_recommended", 0)

        # 0/1 int, "0"/"1", "Y"/"N" 모두 처리
        if isinstance(value, str):
            is_rec = value.upper() in ("Y", "1", "TRUE")
        else:
            is_rec = bool(value)

        rec_flag = " (추천)" if is_rec else ""

        # price가 문자열이면 숫자로 캐스팅
        try:
            price_int = int(price)
        except Exception:
            price_int = price

        lines.append(f"- {menu_name} ({menu_type}, {price}원){rec_flag}")

    return "\n".join(lines)