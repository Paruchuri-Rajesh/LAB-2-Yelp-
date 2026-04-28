from datetime import datetime

from fastapi import APIRouter, Depends

from app.database import get_db
from app.dependencies import get_current_user
from app.models import doc_out
from app.schemas.preferences import PreferencesRead, PreferencesUpdate

router = APIRouter()


async def _get_or_create_prefs(user_id: str) -> dict:
    db = get_db()
    existing = await db.preferences.find_one({"user_id": user_id})
    if existing:
        return doc_out(existing)
    now = datetime.utcnow()
    doc = {"user_id": user_id, "search_radius_miles": 10, "sort_preference": "rating", "updated_at": now}
    result = await db.preferences.insert_one(doc)
    saved = await db.preferences.find_one({"_id": result.inserted_id})
    return doc_out(saved)


@router.get("/me/preferences", response_model=PreferencesRead)
async def get_preferences(current_user=Depends(get_current_user)):
    return await _get_or_create_prefs(current_user["id"])


@router.put("/me/preferences", response_model=PreferencesRead)
async def update_preferences(data: PreferencesUpdate, current_user=Depends(get_current_user)):
    db = get_db()
    await _get_or_create_prefs(current_user["id"])
    update_data = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    update_data["updated_at"] = datetime.utcnow()
    await db.preferences.update_one({"user_id": current_user["id"]}, {"$set": update_data})
    saved = await db.preferences.find_one({"user_id": current_user["id"]})
    return doc_out(saved)
