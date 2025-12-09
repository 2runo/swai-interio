"""Intent parsing and product candidate selection."""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple

from .products_db import PRODUCTS, Product

DEFAULT_ROOM = "living_room"
DEFAULT_BUDGET = "mid"

ROOM_KEYWORDS: Sequence[Tuple[str, str]] = (
    ("거실", "living_room"),
    ("침실", "bedroom"),
    ("아이방", "kids_room"),
    ("서재", "office"),
    ("주방", "kitchen"),
)

STYLE_KEYWORDS = {
    "북유럽": "scandinavian",
    "스칸디": "scandinavian",
    "내추럴": "natural",
    "모던": "modern",
    "미니멀": "minimal",
    "보헤미안": "boho",
    "라탄": "natural",
    "럭셔리": "luxury",
    "고급": "luxury",
    "컬러": "color_pop",
}

BUDGET_HINTS = {
    "저렴": "low",
    "가성비": "low",
    "합리": "mid",
    "보통": "mid",
    "프리미엄": "high",
    "고급": "high",
}


def parse_intent(message: str | None) -> Dict[str, object]:
    """Extract rough room, style, and budget signals from the user text."""
    text = message or ""
    lower_text = text.lower()
    room_type = DEFAULT_ROOM
    for keyword, room in ROOM_KEYWORDS:
        if keyword in text:
            room_type = room
            break

    style_tags = []
    for keyword, style in STYLE_KEYWORDS.items():
        if keyword in text:
            style_tags.append(style)
    # Deduplicate while preserving order
    style_tags = list(dict.fromkeys(style_tags))

    budget_band = _extract_budget_band(text, lower_text)

    return {
        "room_type": room_type,
        "style_tags": style_tags or ["neutral"],
        "budget_band": budget_band,
    }


def _extract_budget_band(text: str, lower_text: str) -> str:
    for keyword, band in BUDGET_HINTS.items():
        if keyword in text:
            return band

    price_match = re.search(r"(\d+)\s*만", text)
    if price_match:
        amount = int(price_match.group(1))
        if amount <= 150:
            return "low"
        if amount <= 300:
            return "mid"
        return "high"

    if any(token in lower_text for token in ("budget", "affordable")):
        return "low"
    if any(token in lower_text for token in ("premium", "luxury")):
        return "high"
    return DEFAULT_BUDGET


def get_candidate_products(intent: Dict[str, object], limit_per_category: int = 2) -> List[Product]:
    """Filter the catalog down to a small list per category for prompting."""
    room_type = intent.get("room_type", DEFAULT_ROOM)
    style_tags = set(intent.get("style_tags") or [])
    budget_band = intent.get("budget_band")

    def product_score(product: Product) -> int:
        score = 0
        if room_type in product.get("room", []):
            score += 2
        overlap = style_tags.intersection(product.get("style", []))
        score += len(overlap)
        if budget_band and product.get("price_band") == budget_band:
            score += 1
        return score

    sorted_products = sorted(
        PRODUCTS,
        key=lambda product: (product_score(product), -PRODUCTS.index(product)),
        reverse=True,
    )

    picked: List[Product] = []
    per_category_count: Dict[str, int] = {}
    for product in sorted_products:
        category = str(product.get("category", "misc"))
        if product_score(product) == 0 and picked:
            continue
        if per_category_count.get(category, 0) >= limit_per_category:
            continue
        per_category_count[category] = per_category_count.get(category, 0) + 1
        picked.append(product)

    if not picked:
        picked = PRODUCTS[: max(1, limit_per_category * 2)]
    return picked


__all__ = ["parse_intent", "get_candidate_products"]

