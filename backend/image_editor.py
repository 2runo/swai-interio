"""Image editing prompt builder and OpenRouter chat image edit helpers."""

from __future__ import annotations

import base64
import logging
import os
import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests
from openai import OpenAI
try:
    from PIL import Image
except ImportError:  # pragma: no cover - dependency might be missing locally
    Image = None

if Image:
    try:
        _RESAMPLE = Image.Resampling.LANCZOS
    except AttributeError:  # pragma: no cover - Pillow < 9.1
        _RESAMPLE = Image.LANCZOS
else:  # pragma: no cover - Pillow missing
    _RESAMPLE = None

from .products_db import Product

logger = logging.getLogger(__name__)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
    default_headers={
        "HTTP-Referer": "https://swai-app.local",
        "X-Title": "SWAI Interior Planner",
    },
)

DATA_URL_PATTERN = re.compile(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", re.DOTALL)
MODEL_NAME = "google/gemini-2.5-flash-image"


def _product_image_preview_url(image_url: Optional[str]) -> Optional[str]:
    if not image_url:
        return None
    postfix = "w=200&h=200&c=c"
    separator = "&" if "?" in image_url else "?"
    return f"{image_url}{separator}{postfix}"


def build_image_edit_prompt(
    user_message: str,
    intent: Dict[str, object],
    selected_products: List[Product],
) -> List[Dict[str, Any]]:
    """Create ordered multimodal instructions for the image-edit API."""
    _ = intent  # Intent kept for compatibility but not used in the simplified prompt.
    user_text = user_message or "(no text provided)"
    content: List[Dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f'User request: "{user_text}". '
                "Edit the provided room photo by drawing in the listed products. "
                "Arrange everything beautifully to satisfy the request while respecting the existing architecture, lighting, and perspective."
            ),
        }
    ]

    for idx, product in enumerate(selected_products, start=1):
        title = product.get("title") or product.get("name") or f"Product {idx}"
        preview_image = _product_image_preview_url(product.get("img") or "")
        content.append({"type": "text", "text": f"{idx}. Product: {title}"})
        if preview_image:
            content.append({"type": "image_url", "image_url": {"url": preview_image}})

    return content


def edit_room_image(image_url: str, prompt_content: List[Dict[str, Any]]) -> Optional[str]:
    """Call OpenRouter chat completion API and return a data URL with the edited room."""
    if not image_url:
        return None
    print("Image edit input URL: %s", image_url)
    try:
        image_bytes, mime = _load_image_bytes(image_url)
        image_bytes, mime = _ensure_max_dimensions(image_bytes, mime)
    except Exception as error:
        logger.error("Unable to load user image: %s", error)
        return None

    try:
        data_url = _encode_image_as_data_url(image_bytes, mime)
        content = list(prompt_content)
        content.append({"type": "text", "text": "User's room photo:"})
        content.append({"type": "image_url", "image_url": {"url": data_url}})
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            modalities=["image", "text"],
        )
        edited_image_url = _extract_image_data_url(response)
        if not edited_image_url:
            logger.error("Image edit request returned no images.")
            return None
        print("Image edit output (data URL): %s", edited_image_url)
        return edited_image_url
    except Exception as error:
        logger.exception("Image edit request failed: %s", error)
        return None


def _load_image_bytes(image_url: str) -> Tuple[bytes, str]:
    if image_url.startswith("data:"):
        match = DATA_URL_PATTERN.match(image_url)
        if not match:
            raise ValueError("Invalid data URL")
        return base64.b64decode(match.group("data")), match.group("mime")
    response = requests.get(image_url, timeout=15)
    response.raise_for_status()
    mime = response.headers.get("content-type", "image/png")
    return response.content, mime


def _encode_image_as_data_url(image_bytes: bytes, mime: Optional[str]) -> str:
    safe_mime = mime or "image/png"
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{safe_mime};base64,{b64}"


def _ensure_max_dimensions(
    image_bytes: bytes,
    mime: Optional[str],
    max_side: int = 700,
) -> Tuple[bytes, str]:
    """Resize the user-provided image proportionally to fit within max_side."""
    if not Image:
        return image_bytes, mime or "image/png"

    try:
        with Image.open(BytesIO(image_bytes)) as img:
            width, height = img.size
            if width <= max_side and height <= max_side:
                inferred_mime = mime or Image.MIME.get(img.format, "image/png")
                return image_bytes, inferred_mime

            scale = min(max_side / float(width), max_side / float(height))
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            resample = _RESAMPLE or getattr(Image, "LANCZOS", Image.BICUBIC)
            resized = img.resize(new_size, resample)

            if resized.mode not in ("RGB", "RGBA"):
                resized = resized.convert("RGB")

            buffer = BytesIO()
            save_format = "PNG" if resized.mode == "RGBA" else "JPEG"
            output_mime = "image/png" if save_format == "PNG" else "image/jpeg"
            save_kwargs = {"quality": 90} if save_format == "JPEG" else {}
            resized.save(buffer, format=save_format, **save_kwargs)
            buffer.seek(0)
            return buffer.read(), output_mime
    except Exception as error:  # pragma: no cover - defensive
        logger.warning("Failed to resize user image: %s", error)
        return image_bytes, mime or "image/png"


def _extract_image_data_url(response: Any) -> Optional[str]:
    """Try to extract the first image data URL from the OpenRouter response."""
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, KeyError, TypeError):
        return None

    images = getattr(message, "images", None)
    if images:
        first_image = images[0]
        image_url = getattr(first_image, "image_url", None)
        if hasattr(image_url, "url"):
            return image_url.url
        if isinstance(image_url, dict):
            return image_url.get("url")
        if isinstance(first_image, dict):
            candidate = first_image.get("image_url")
            if isinstance(candidate, dict):
                return candidate.get("url")

    content = getattr(message, "content", None)
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "image_url":
                image_url = item.get("image_url")
                if isinstance(image_url, dict):
                    url = image_url.get("url")
                    if url:
                        return url

    return None


__all__ = ["build_image_edit_prompt", "edit_room_image"]
