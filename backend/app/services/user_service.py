"""User-related Mongo operations."""
from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status

from app.database import get_db
from app.models import doc_out, to_object_id
from app.schemas.auth import SignupRequest
from app.schemas.user import UserUpdate
from app.services.auth_service import get_password_hash


def _shape_user(doc: dict) -> dict:
    out = doc_out(doc) or {}
    out["is_owner"] = bool(out.get("owner_profile"))
    out["account_type"] = "owner" if out["is_owner"] else "user"
    return out


async def get_user_by_email(email: str) -> dict | None:
    doc = await get_db().users.find_one({"email": email.lower()})
    return _shape_user(doc) if doc else None


async def get_user_by_id(user_id: str) -> dict | None:
    oid = to_object_id(user_id)
    if not oid:
        return None
    doc = await get_db().users.find_one({"_id": oid})
    return _shape_user(doc) if doc else None


async def create_user(data: SignupRequest) -> dict:
    db = get_db()
    if await db.users.find_one({"email": data.email.lower()}):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    now = datetime.utcnow()
    doc: dict[str, Any] = {
        "name": data.name,
        "email": data.email.lower(),
        "hashed_password": get_password_hash(data.password),
        "phone": None,
        "about_me": None,
        "city": None,
        "state": None,
        "country": None,
        "languages": None,
        "gender": None,
        "profile_picture_path": None,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    if data.account_type == "owner":
        doc["owner_profile"] = {
            "business_name": data.business_name,
            "restaurant_location": data.restaurant_location,
            "bio": None,
            "created_at": now,
            "updated_at": now,
        }
    result = await db.users.insert_one(doc)
    created = await db.users.find_one({"_id": result.inserted_id})
    return _shape_user(created)


async def update_user(user_id: str, data: UserUpdate) -> dict:
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        return await get_user_by_id(user_id)
    update_data["updated_at"] = datetime.utcnow()
    await get_db().users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    return await get_user_by_id(user_id)


async def set_avatar(user_id: str, relative_path: str) -> dict:
    await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"profile_picture_path": relative_path, "updated_at": datetime.utcnow()}},
    )
    return await get_user_by_id(user_id)


async def remove_avatar(user_id: str) -> dict:
    await get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"profile_picture_path": None, "updated_at": datetime.utcnow()}},
    )
    return await get_user_by_id(user_id)


async def add_favorite(user_id: str, restaurant_id: str) -> None:
    db = get_db()
    r_oid = to_object_id(restaurant_id)
    if not r_oid or not await db.restaurants.find_one({"_id": r_oid}):
        raise ValueError("Restaurant not found")
    await db.favorites.update_one(
        {"user_id": user_id, "restaurant_id": str(r_oid)},
        {"$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True,
    )


async def remove_favorite(user_id: str, restaurant_id: str) -> None:
    await get_db().favorites.delete_one({"user_id": user_id, "restaurant_id": str(restaurant_id)})


async def list_favorites(user_id: str, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
    db = get_db()
    total = await db.favorites.count_documents({"user_id": user_id})
    cursor = (
        db.favorites.find({"user_id": user_id})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    favorites = [f async for f in cursor]
    restaurant_ids = [to_object_id(f["restaurant_id"]) for f in favorites]
    restaurant_ids = [oid for oid in restaurant_ids if oid is not None]
    if not restaurant_ids:
        return [], total
    r_cursor = db.restaurants.find({"_id": {"$in": restaurant_ids}, "is_closed": {"$ne": True}})
    by_id = {str(r["_id"]): r async for r in r_cursor}
    ordered = [by_id[f["restaurant_id"]] for f in favorites if f["restaurant_id"] in by_id]
    return [doc_out(r) for r in ordered], total


async def is_favorited(user_id: str | None, restaurant_id: str) -> bool:
    if not user_id:
        return False
    doc = await get_db().favorites.find_one({"user_id": user_id, "restaurant_id": restaurant_id})
    return doc is not None
