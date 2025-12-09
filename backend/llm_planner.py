"""Planner that asks OpenAI to pick final products and craft the reply."""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Tuple, TypedDict

from openai import OpenAI

from .products_db import Product, PRODUCTS

logger = logging.getLogger(__name__)
client = OpenAI()


class PlanningResult(TypedDict):
    selected_product_ids: List[str]
    assistant_message: str


def plan_products_with_llm(
    user_message: str,
    intent: Dict[str, object],
    candidate_products: List[Product],
) -> PlanningResult:
    """Use ChatGPT to pick products and craft a user-facing response."""
    if not candidate_products:
        return _fallback_plan(candidate_products, "추천할 후보 제품을 찾지 못했어요.")

    messages = _build_messages(user_message, intent, candidate_products)
    try:
        print(
            "LLM planner input messages:\n%s",
            json.dumps(messages, ensure_ascii=False, indent=2),
        )
    except Exception:
        print("LLM planner input messages: %s", messages)

    try:
        response = client.chat.completions.create(
            model="gpt-5",
            messages=messages,
        )
        content = response.choices[0].message.content or ""
        print("LLM planner raw output:\n%s", content)
        plan = _parse_plan_json(content)
        if not plan["selected_product_ids"]:
            raise ValueError("No products chosen by planner")
        return plan
    except Exception as error:
        logger.exception("Planner failed, falling back: %s", error)
        return _fallback_plan(candidate_products, "AI 플래너 오류가 발생하여 기본 추천을 보여드려요.")


def _build_messages(
    user_message: str,
    intent: Dict[str, object],
    candidates: List[Product],
) -> List[Dict[str, str]]:
    system_prompt = (
        "You are an interior stylist and recommendation planner. "
        "Choose the most relevant products from the candidate list and craft a short Korean message "
        "summarizing the layout and why these products match. Respond strictly in JSON."
    )

    user_prompt = (
        f"Raw user message:\n{user_message or '(no text, image only)'}\n\n"
        "Candidate products:\n"
        + json.dumps(PRODUCTS, ensure_ascii=False, indent=2)
        + "\n\nReturn JSON in this exact shape:\n"
        '{\n'
        '  "selected_products": ["product_id_1", "product_id_2"],\n'
        '  "assistant_message": "한국어로 된 설명"\n'
        "}\n"
        "Respond with JSON only. Do not include any additional text."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _parse_plan_json(raw_content: str) -> PlanningResult:
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError:
        sanitized = raw_content.strip()
        start = sanitized.find("{")
        end = sanitized.rfind("}")
        if start == -1 or end == -1:
            raise
        payload = json.loads(sanitized[start : end + 1])

    selected_ids = payload.get("selected_products") or []
    assistant_message = payload.get("assistant_message") or ""
    return PlanningResult(
        selected_product_ids=[str(pid) for pid in selected_ids],
        assistant_message=assistant_message.strip() or "추천 제품을 확인해보세요.",
    )


def _fallback_plan(candidate_products: List[Product], reason: str) -> PlanningResult:
    picks = candidate_products[:3]
    selected_ids = [product["id"] for product in picks]
    lines = [reason, ""] if reason else []
    lines.append("아래 제품을 공간에 맞게 활용해 보세요:")
    for product in picks:
        title = product.get("title") or product.get("name") or "제품"
        price = product.get("price") or "가격 미정"
        lines.append(f"- {title} ({price})")
    message = "\n".join(lines)
    return PlanningResult(
        selected_product_ids=selected_ids,
        assistant_message=message,
    )


__all__ = ["plan_products_with_llm"]
