"""FastAPI application that powers the interio AI assistant backend."""

from __future__ import annotations

import logging
import os
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .secure_env import ensure_encrypted_env

ensure_encrypted_env()

from .image_editor import build_image_edit_prompt, edit_room_image
from .intent import get_candidate_products, parse_intent
from .llm_planner import plan_products_with_llm
from .products_db import PRODUCT_INDEX, PRODUCTS, Product

logger = logging.getLogger(__name__)

app = FastAPI(title="Interio AI Backend", version="0.1.0")

_default_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
allowed_origins_env = os.getenv("BACKEND_ALLOWED_ORIGINS")
allowed_origins = (
    [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    if allowed_origins_env
    else _default_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HistoryEntry(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    imageUrl: Optional[str] = None


class ChatRequest(BaseModel):
    message: Optional[str] = ""
    imageUrl: Optional[str] = None
    history: List[HistoryEntry] = Field(default_factory=list)


class ProductCard(BaseModel):
    img: str
    title: str
    price: str
    link: str


class ChatResponse(BaseModel):
    text: str
    imageUrl: Optional[str] = None
    products: List[ProductCard] = Field(default_factory=list)


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Handle chat requests coming from the frontend."""
    try:
        user_message = request.message or ""
        intent = parse_intent(user_message)
        candidate_products = get_candidate_products(intent)
        plan = plan_products_with_llm(user_message, intent, candidate_products)

        selected_products = _lookup_products(plan["selected_product_ids"])
        if not selected_products:
            selected_products = candidate_products[:3] or PRODUCTS[:3]

        edited_image_url = None
        if request.imageUrl:
            prompt_content = build_image_edit_prompt(user_message, intent, selected_products)
            edited_image_url = edit_room_image(request.imageUrl, prompt_content)

        return ChatResponse(
            text=plan["assistant_message"],
            imageUrl=edited_image_url,
            products=[_product_to_card(product) for product in selected_products],
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Unexpected error handling /chat: %s", error)
        raise HTTPException(status_code=500, detail="서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")


def _lookup_products(product_ids: List[str]) -> List[Product]:
    items = []
    for product_id in product_ids:
        product = PRODUCT_INDEX.get(product_id)
        if product:
            items.append(product)
    return items


def _product_to_card(product: Product) -> ProductCard:
    title = product.get("title") or product.get("name") or "추천 제품"
    image = product.get("img") or product.get("thumbnail") or ""
    price = product.get("price") or ""
    link = product.get("link") or ""
    return ProductCard(
        img=str(image),
        title=str(title),
        price=str(price),
        link=str(link),
    )


__all__ = ["app"]
