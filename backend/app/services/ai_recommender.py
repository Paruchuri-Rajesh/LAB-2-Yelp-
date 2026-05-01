"""Lightweight Mongo-backed restaurant recommender for the AI chat widget.

This is a pragmatic Lab-2 port of the Lab-1 ``ai_agent``. The Lab-1 service
was 1k+ lines of SQLAlchemy + Ollama orchestration; here we keep the same
external contract (``assistant_text`` + ``recommendations`` + streaming
events) but power it with the Mongo data already seeded by Lab-2 plus
simple keyword parsing. If ``OLLAMA_URL``/``OLLAMA_MODEL`` are configured
the assistant text is replaced by an LLM-generated blurb; otherwise we
fall back to a templated response so the widget works out of the box.
"""
from __future__ import annotations

import re
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from app.config import settings
from app.database import get_db


PRICE_KEYWORDS = {
    "$": ["cheap", "budget", "affordable", "inexpensive", "$"],
    "$$": ["mid", "moderate", "$$"],
    "$$$": ["upscale", "fancy", "expensive", "$$$"],
    "$$$$": ["fine dining", "luxury", "$$$$"],
}

CUISINE_KEYWORDS = [
    "italian", "mexican", "chinese", "japanese", "thai", "indian",
    "french", "american", "korean", "vietnamese", "mediterranean",
    "greek", "spanish", "ethiopian", "turkish", "bbq", "sushi",
    "pizza", "burger", "ramen", "taco", "vegan", "vegetarian",
    "seafood", "steakhouse", "cafe", "coffee", "brunch", "breakfast",
]


def _parse_filters(message: str) -> Dict[str, Any]:
    text = (message or "").lower()
    filters: Dict[str, Any] = {}

    for symbol, words in PRICE_KEYWORDS.items():
        if any(w in text for w in words):
            filters["price_range"] = symbol
            break

    for cuisine in CUISINE_KEYWORDS:
        if cuisine in text:
            filters["cuisine"] = cuisine
            break

    rating_match = re.search(r"(\d(?:\.\d)?)\s*(?:\+|stars?|or higher)", text)
    if rating_match:
        try:
            filters["min_rating"] = float(rating_match.group(1))
        except ValueError:
            pass

    if "near me" in text or "nearby" in text or "close by" in text:
        filters["near_me"] = True

    return filters


def _build_mongo_query(filters: Dict[str, Any]) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if (cuisine := filters.get("cuisine")):
        q["$or"] = [
            {"cuisine_type": {"$regex": cuisine, "$options": "i"}},
            {"name": {"$regex": cuisine, "$options": "i"}},
            {"description": {"$regex": cuisine, "$options": "i"}},
        ]
    if (price := filters.get("price_range")):
        q["price_range"] = price
    if (min_rating := filters.get("min_rating")):
        q["avg_rating"] = {"$gte": min_rating}
    return q


async def _fetch_candidates(filters: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    db = get_db()
    query = _build_mongo_query(filters)
    cursor = db.restaurants.find(query).sort([("avg_rating", -1), ("review_count", -1)]).limit(limit)
    docs = [doc async for doc in cursor]

    if not docs and query:
        cursor = db.restaurants.find({}).sort([("avg_rating", -1), ("review_count", -1)]).limit(limit)
        docs = [doc async for doc in cursor]
    return docs


def _doc_to_recommendation(doc: Dict[str, Any], reason: str) -> Dict[str, Any]:
    raw_id = doc.get("id") or doc.get("_id")
    return {
        "id": str(raw_id) if raw_id is not None else "",
        "name": doc.get("name") or "Unnamed restaurant",
        "avg_rating": float(doc["avg_rating"]) if doc.get("avg_rating") is not None else None,
        "review_count": int(doc["review_count"]) if doc.get("review_count") is not None else None,
        "price_range": doc.get("price_range"),
        "cuisine_type": doc.get("cuisine_type"),
        "address": doc.get("address"),
        "city": doc.get("city"),
        "state": doc.get("state"),
        "image_url": doc.get("image_url"),
        "primary_photo": doc.get("primary_photo") or doc.get("image_url"),
        "source": doc.get("source") or "local",
        "latitude": doc.get("latitude"),
        "longitude": doc.get("longitude"),
        "reason": reason,
    }


def _build_reason(doc: Dict[str, Any], filters: Dict[str, Any]) -> str:
    parts: List[str] = []
    if filters.get("cuisine"):
        parts.append(f"matches your {filters['cuisine']} preference")
    if filters.get("price_range"):
        parts.append(f"in your {filters['price_range']} budget")
    if doc.get("avg_rating"):
        parts.append(f"rated {doc['avg_rating']:.1f}")
    if doc.get("review_count"):
        parts.append(f"{doc['review_count']} reviews")
    if not parts:
        parts.append("popular pick")
    return ", ".join(parts).capitalize()


async def _ollama_blurb(message: str, recommendations: List[Dict[str, Any]]) -> Optional[str]:
    if not settings.OLLAMA_URL or not settings.OLLAMA_MODEL:
        return None
    names = ", ".join(r["name"] for r in recommendations[:5]) or "no matches"
    prompt = (
        "You are a concise restaurant concierge. The user asked: "
        f"'{message}'. Recommended restaurants: {names}. "
        "In 1-2 friendly sentences, summarize the picks."
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.OLLAMA_URL.rstrip('/')}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
            )
            response.raise_for_status()
            data = response.json()
            text = (data.get("response") or "").strip()
            return text or None
    except Exception:
        return None


def _template_blurb(message: str, recommendations: List[Dict[str, Any]], filters: Dict[str, Any]) -> str:
    if not recommendations:
        return (
            "I couldn't find any restaurants matching that yet. "
            "Try asking for a cuisine like 'show me Italian places' or 'cheap sushi'."
        )
    descriptors: List[str] = []
    if filters.get("cuisine"):
        descriptors.append(f"{filters['cuisine']}")
    if filters.get("price_range"):
        descriptors.append(f"{filters['price_range']}")
    if filters.get("min_rating"):
        descriptors.append(f"{filters['min_rating']}+ stars")
    descriptor = " ".join(descriptors) if descriptors else "top-rated"
    names = ", ".join(r["name"] for r in recommendations[:3])
    return f"Here are {descriptor} picks I found: {names}."


async def generate_recommendations_payload(
    message: str,
    conversation_history: Optional[List[Any]] = None,
    client_location: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    filters = _parse_filters(message)
    docs = await _fetch_candidates(filters, limit=5)
    recommendations = [_doc_to_recommendation(d, _build_reason(d, filters)) for d in docs]

    blurb = await _ollama_blurb(message, recommendations) or _template_blurb(message, recommendations, filters)

    return {
        "assistant_text": blurb,
        "recommendations": recommendations,
        "parsed_filters": filters,
        "route": None,
        "used_current_context": bool(client_location),
    }


async def stream_recommendations(
    message: str,
    conversation_history: Optional[List[Any]] = None,
    client_location: Optional[Dict[str, float]] = None,
) -> AsyncGenerator[tuple[str, Any], None]:
    payload = await generate_recommendations_payload(message, conversation_history, client_location)

    text = payload["assistant_text"]
    chunk_size = 60
    for i in range(0, len(text), chunk_size):
        yield ("assistant_chunk", text[i : i + chunk_size])

    for item in payload["recommendations"]:
        yield ("recommendation", item)
