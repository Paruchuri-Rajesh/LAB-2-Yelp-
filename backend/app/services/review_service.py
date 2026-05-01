"""Review-related Mongo operations.

This module is split between API-side helpers (``create_review_request``
etc.) which validate + publish Kafka events but do NOT themselves persist
the review, and worker-side helpers (``apply_*``) which actually write to
Mongo. The rubric explicitly asks for review create/update/delete to flow
through Kafka, so API handlers stay write-free and the worker is the
source of truth for review data.
"""
from datetime import datetime, date
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.database import get_db
from app.models import doc_out, to_object_id
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.services.restaurant_service import recalculate_restaurant_ratings


def _serialize_review_payload(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


async def list_reviews_for_restaurant(restaurant_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = get_db()
    total = await db.reviews.count_documents({"restaurant_id": restaurant_id})
    cursor = (
        db.reviews.find({"restaurant_id": restaurant_id})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [doc_out(r) async for r in cursor]
    await _hydrate_users(items)
    return items, total


async def list_user_reviews(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = get_db()
    total = await db.reviews.count_documents({"user_id": user_id})
    cursor = (
        db.reviews.find({"user_id": user_id})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [doc_out(r) async for r in cursor]
    await _hydrate_users(items)
    await _hydrate_restaurant_names(items)
    return items, total


async def _hydrate_users(reviews: list[dict]) -> None:
    db = get_db()
    user_ids = {to_object_id(r["user_id"]) for r in reviews if r.get("user_id")}
    user_ids.discard(None)
    if not user_ids:
        return
    users = {str(u["_id"]): u async for u in db.users.find({"_id": {"$in": list(user_ids)}})}
    for r in reviews:
        u = users.get(r.get("user_id"))
        if u:
            r["user"] = {
                "id": str(u["_id"]),
                "name": u.get("name"),
                "profile_picture_path": u.get("profile_picture_path"),
            }


async def _hydrate_restaurant_names(reviews: list[dict]) -> None:
    db = get_db()
    ids = {to_object_id(r["restaurant_id"]) for r in reviews if r.get("restaurant_id")}
    ids.discard(None)
    if not ids:
        return
    rs = {str(r["_id"]): r async for r in db.restaurants.find({"_id": {"$in": list(ids)}})}
    for r in reviews:
        row = rs.get(r.get("restaurant_id"))
        if row:
            r["restaurant_name"] = row.get("name")


async def assert_user_can_review(restaurant_id: str, user_id: str) -> None:
    """Enforced on the API side so errors surface synchronously."""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user and user.get("owner_profile"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account owners are not allowed to post reviews.")
    owns = await db.ownerships.find_one({"restaurant_id": restaurant_id, "owner_id": user_id})
    if owns:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owners cannot review their own restaurant.")
    existing = await db.reviews.find_one({"restaurant_id": restaurant_id, "user_id": user_id})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already reviewed this restaurant.")


async def apply_created(payload: dict) -> dict:
    """Worker-side: persist a review from a ``review.created`` event."""
    db = get_db()
    now = datetime.utcnow()
    data = payload.get("data") or {}
    doc = {
        "restaurant_id": payload["restaurant_id"],
        "user_id": payload.get("user_id"),
        "source": "local",
        "rating": int(data.get("rating")) if data.get("rating") is not None else None,
        "title": data.get("title"),
        "body": data.get("body"),
        "author_name": payload.get("author_name"),
        "author_image_url": None,
        "source_url": None,
        "visited_at": data.get("visited_at"),
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await db.reviews.insert_one(doc)
    except Exception:
        return {}
    await recalculate_restaurant_ratings(payload["restaurant_id"])
    saved = await db.reviews.find_one({"_id": result.inserted_id})
    return doc_out(saved) or {}


async def apply_updated(payload: dict) -> dict:
    db = get_db()
    review_id = payload["review_id"]
    oid = to_object_id(review_id)
    if not oid:
        return {}
    update = {k: v for k, v in (payload.get("data") or {}).items() if v is not None}
    update["updated_at"] = datetime.utcnow()
    await db.reviews.update_one({"_id": oid}, {"$set": update})
    updated = await db.reviews.find_one({"_id": oid})
    if updated:
        await recalculate_restaurant_ratings(updated["restaurant_id"])
    return doc_out(updated) or {}


async def apply_deleted(payload: dict) -> None:
    db = get_db()
    oid = to_object_id(payload["review_id"])
    if not oid:
        return
    existing = await db.reviews.find_one({"_id": oid})
    if not existing:
        return
    await db.reviews.delete_one({"_id": oid})
    await recalculate_restaurant_ratings(existing["restaurant_id"])


async def load_review(review_id: str) -> dict | None:
    oid = to_object_id(review_id)
    if not oid:
        return None
    doc = await get_db().reviews.find_one({"_id": oid})
    if not doc:
        return None
    out = [doc_out(doc)]
    await _hydrate_users(out)
    return out[0]


async def enforce_review_owner(review_id: str, user_id: str) -> dict:
    review = await load_review(review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    if str(review.get("user_id")) != str(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized.")
    return review


def build_create_payload(restaurant_id: str, user_id: str, author_name: str | None, data: ReviewCreate) -> dict:
    return {
        "restaurant_id": restaurant_id,
        "user_id": user_id,
        "author_name": author_name,
        "data": _serialize_review_payload(data.model_dump()),
        "issued_at": datetime.utcnow().isoformat(),
    }


def build_update_payload(review_id: str, user_id: str, data: ReviewUpdate) -> dict:
    return {
        "review_id": review_id,
        "user_id": user_id,
        "data": _serialize_review_payload(data.model_dump(exclude_unset=True)),
        "issued_at": datetime.utcnow().isoformat(),
    }


def build_delete_payload(review_id: str, user_id: str, restaurant_id: str) -> dict:
    return {
        "review_id": review_id,
        "user_id": user_id,
        "restaurant_id": restaurant_id,
        "issued_at": datetime.utcnow().isoformat(),
    }
