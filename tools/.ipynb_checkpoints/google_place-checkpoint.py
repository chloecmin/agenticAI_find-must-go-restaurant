# tools/google_places.py

import os
from typing import List, Dict, Any, Optional
import requests

# Google Places API 엔드포인트
TEXT_ENDPOINT = "https://maps.googleapis.com/maps/api/place/textsearch/json"
NEARBY_ENDPOINT = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


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
                "name": r.get("name"),
                "address": r.get("vicinity"),  # nearbysearch에서는 formatted_address 대신 vicinity 사용
                "location": r.get("geometry", {}).get("location"),
                "rating": r.get("rating"),
                "user_ratings_total": r.get("user_ratings_total"),
                "types": r.get("types"),
            }
        )
    return places
