# tools/google_places.py

import os
from typing import List, Dict, Any, Optional
import requests

# Google Places API 엔드포인트
TEXT_ENDPOINT = "https://maps.googleapis.com/maps/api/place/textsearch/json"
NEARBY_ENDPOINT = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_ENDPOINT = "https://maps.googleapis.com/maps/api/place/details/json"


def _get_api_key() -> str:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY가 설정되지 않았습니다. .env를 확인하세요.")
    return api_key


# --------------------------------------------------
# 1) 기존: 텍스트 기반 검색 (query 문자열로 검색)
# --------------------------------------------------

def search_place(
    query: str,
    region: Optional[str] = None,
    language: str = "ko",
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Google Places Text Search API를 사용해서 query(예: '홍대 텐동')로 장소를 검색한다.

    반환값: 각 결과는
    {
      "name": str,
      "address": str,
      "location": {"lat": float, "lng": float},
      "rating": float | None,
      "user_ratings_total": int | None,
      "types": List[str] | None,
    }
    형태의 dict.
    """
    api_key = _get_api_key()

    params = {
        "key": api_key,
        "query": query,
        "language": language,
    }
    if region:
        params["region"] = region

    resp = requests.get(TEXT_ENDPOINT, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])[:limit]

    places: List[Dict[str, Any]] = []
    for r in results:
        places.append(
            {
                "place_id": r.get("place_id"),  # place_id 추가
                "name": r.get("name"),
                "address": r.get("formatted_address"),
                "location": r.get("geometry", {}).get("location"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("user_ratings_total"),
                "types": r.get("types"),
            }
        )
    return places


# --------------------------------------------------
# 2) 새로 추가: 위도/경도로 검색 (Nearby Search)
# --------------------------------------------------

def search_place_by_location(
    latitude: float,
    longitude: float,
    keyword: Optional[str] = None,
    radius: int = 150,
    language: str = "ko",
) -> List[Dict[str, Any]]:
    """
    위도/경도 주변의 장소를 검색하는 함수.
    - es_search_tool에서 가져온 (lat, lon) 기준으로 주변 식당을 찾을 수 있다.
    - keyword를 함께 주면, 해당 키워드에 맞는 곳을 우선적으로 탐색할 수 있다.
      (예: keyword='텐동야' 또는 '텐동')

    반환값 형식은 search_place와 동일.
    """
    api_key = _get_api_key()

    params = {
        "key": api_key,
        "location": f"{latitude},{longitude}",
        "radius": radius,      # 미터 단위. 테스트용이면 100~200 정도로 충분
        "language": language,
    }
    if keyword:
        params["keyword"] = keyword

    resp = requests.get(NEARBY_ENDPOINT, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])

    places: List[Dict[str, Any]] = []
    for r in results:
        places.append(
            {
                "place_id": r.get("place_id"),  # place_id 추가
                "name": r.get("name"),
                "address": r.get("vicinity"),  # nearbysearch에서는 formatted_address 대신 vicinity 사용
                "location": r.get("geometry", {}).get("location"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("user_ratings_total"),
                "types": r.get("types"),
            }
        )
    return places


# --------------------------------------------------
# 3) Place Details API: place_id로 상세 정보 및 리뷰 가져오기
# --------------------------------------------------

def get_place_details(
    place_id: str,
    language: str = "ko",
) -> Dict[str, Any]:
    """
    Place Details API를 사용해서 특정 장소의 상세 정보와 리뷰를 가져온다.
    
    Args:
        place_id: Google Places API의 place_id
        language: 언어 코드 (기본값: "ko")
    
    Returns:
        {
            "name": str,
            "address": str,
            "rating": float,
            "user_ratings_total": int,
            "reviews": List[Dict],  # 리뷰 리스트 (상위 3개)
            "phone_number": str,  # 전화번호
            "opening_hours": List[str]  # 요일별 영업시간
        }
    """
    api_key = _get_api_key()
    
    params = {
        "key": api_key,
        "place_id": place_id,
        "language": language,
        "fields": "name,formatted_address,rating,user_ratings_total,reviews,formatted_phone_number,opening_hours",  # 필요한 필드만 요청
    }
    
    resp = requests.get(DETAILS_ENDPOINT, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    result = data.get("result", {})
    
    # 리뷰는 상위 3개만
    reviews = result.get("reviews", [])[:3]
    
    # 영업시간 추출
    opening_hours = []
    opening_hours_data = result.get("opening_hours", {})
    if opening_hours_data:
        weekday_text = opening_hours_data.get("weekday_text", [])
        opening_hours = weekday_text if weekday_text else []
    
    return {
        "name": result.get("name"),
        "address": result.get("formatted_address"),
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total"),
        "reviews": reviews,  # 상위 3개만
        "phone_number": result.get("formatted_phone_number"),
        "opening_hours": opening_hours,  # 요일별 영업시간
    }


def get_place_reviews_by_name_and_location(
    restaurant_name: str,
    latitude: float,
    longitude: float,
    language: str = "ko",
) -> Dict[str, Any]:
    """
    식당 이름과 위도/경도를 사용해서 Google Places에서 리뷰를 가져온다.
    
    절차:
    1. 위도/경도로 Nearby Search를 해서 식당 이름과 매칭되는 place_id 찾기
    2. place_id로 Place Details API 호출해서 리뷰 가져오기
    
    Args:
        restaurant_name: 식당 이름
        latitude: 위도
        longitude: 경도
        language: 언어 코드
    
    Returns:
        get_place_details와 동일한 형식
    """
    # 1단계: Nearby Search로 place_id 찾기
    places = search_place_by_location(
        latitude=latitude,
        longitude=longitude,
        keyword=restaurant_name,
        radius=100,  # 100m 반경으로 좁혀서 정확도 높이기
        language=language,
    )
    
    if not places:
        return {
            "name": restaurant_name,
            "address": None,
            "rating": None,
            "user_ratings_total": 0,
            "reviews": [],
            "phone_number": None,
            "opening_hours": [],
        }
    
    # 식당 이름과 가장 유사한 결과 찾기
    best_match = None
    for place in places:
        place_name = place.get("name", "").lower()
        if restaurant_name.lower() in place_name or place_name in restaurant_name.lower():
            best_match = place
            break
    
    # 매칭되는 게 없으면 첫 번째 결과 사용
    if not best_match:
        best_match = places[0]
    
    # place_id가 있으면 Place Details API 호출
    place_id = best_match.get("place_id")
    if place_id:
        try:
            return get_place_details(place_id, language)
        except Exception as e:
            # Place Details API 실패 시 기본 정보만 반환
            return {
                "name": best_match.get("name", restaurant_name),
                "address": best_match.get("address"),
                "rating": best_match.get("rating"),
                "user_ratings_total": best_match.get("user_ratings_total", 0),
                "reviews": [],
                "phone_number": None,
                "opening_hours": [],
            }
    
    # place_id가 없으면 기본 정보만 반환
    return {
        "name": best_match.get("name", restaurant_name),
        "address": best_match.get("address"),
        "rating": best_match.get("rating"),
        "user_ratings_total": best_match.get("user_ratings_total", 0),
        "reviews": [],
        "phone_number": None,
        "opening_hours": [],
    }
