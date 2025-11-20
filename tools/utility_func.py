from __future__ import annotations
from typing import Union, Optional, Tuple, List, Dict
import csv
from pathlib import Path

Number = Union[int, float]


def calculator(expression: str) -> Number:
    """
    매우 단순한 사칙연산 계산기.
    eval은 위험하니, 실제 운영에서는 안전한 파서/라이브러리를 쓰는 것이 좋다.
    """
    try:
        return eval(expression, {"__builtins__": {}}, {})
    except Exception as e:
        raise ValueError(f"잘못된 수식입니다: {expression}") from e


def load_menus_for_restaurant(
    restaurant_name: str,
    csv_path: str | Path,
) -> List[Dict[str, str]]:
    """
    menu CSV에서 특정 식당(restaurant_name)의 모든 메뉴 row를 반환.
    - restaurant_id, restaurant_name, menu_name, menu_type, price, is_recommended 등 포함.
    """
    csv_path = Path(csv_path)
    rows: List[Dict[str, str]] = []

    with csv_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("restaurant_name") == restaurant_name:
                rows.append(row)

    return rows
