import math

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, status

from app.dependencies import get_current_user
from app.schemas.user import UserRead, UserUpdate
from app.schemas.review import ReviewsResponse
from app.schemas.restaurant import RestaurantListItem
from app.services.user_service import (
    update_user, set_avatar, remove_avatar,
    add_favorite, remove_favorite, list_favorites,
)
from app.services.file_service import save_profile_picture, delete_file
from app.services.review_service import list_user_reviews
from app.kafka_utils import Topics, publish_event

router = APIRouter()


@router.get("/me", response_model=UserRead)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserRead)
async def update_me(data: UserUpdate, current_user=Depends(get_current_user)):
    updated = await update_user(current_user["id"], data)
    await publish_event(Topics.USER_UPDATED, {
        "user_id": current_user["id"],
        "changes": data.model_dump(exclude_unset=True),
    }, key=current_user["id"])
    return updated


@router.post("/me/avatar", response_model=UserRead)
async def upload_avatar(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    old_path = current_user.get("profile_picture_path")
    relative_path = await save_profile_picture(file)
    user = await set_avatar(current_user["id"], relative_path)
    if old_path:
        delete_file(old_path)
    return user


@router.delete("/me/avatar", response_model=UserRead)
async def delete_avatar(current_user=Depends(get_current_user)):
    old_path = current_user.get("profile_picture_path")
    user = await remove_avatar(current_user["id"])
    if old_path:
        delete_file(old_path)
    return user


@router.get("/me/reviews", response_model=ReviewsResponse)
async def my_reviews(page: int = 1, page_size: int = 20, current_user=Depends(get_current_user)):
    items, total = await list_user_reviews(current_user["id"], page, page_size)
    return ReviewsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("/me/favorites/{restaurant_id}", status_code=204)
async def favorite_restaurant(restaurant_id: str, current_user=Depends(get_current_user)):
    try:
        await add_favorite(current_user["id"], restaurant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/favorites/{restaurant_id}", status_code=204)
async def unfavorite_restaurant(restaurant_id: str, current_user=Depends(get_current_user)):
    await remove_favorite(current_user["id"], restaurant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me/favorites")
async def my_favorites(page: int = 1, page_size: int = 20, current_user=Depends(get_current_user)):
    items, total = await list_favorites(current_user["id"], page, page_size)
    list_items = [
        RestaurantListItem(
            id=r["id"],
            name=r.get("name") or "",
            slug=r.get("slug"),
            cuisine_type=r.get("cuisine_type"),
            city=r.get("city"),
            state=r.get("state"),
            address=r.get("address"),
            zip_code=r.get("zip_code"),
            price_range=r.get("price_range"),
            avg_rating=float(r.get("avg_rating") or 0),
            review_count=int(r.get("review_count") or 0),
            primary_photo=(r.get("photos") or [{}])[0].get("file_path") if r.get("photos") else r.get("image_url"),
            latitude=r.get("latitude"),
            longitude=r.get("longitude"),
            source=r.get("source") or "local",
            is_favorited=True,
        ).model_dump()
        for r in items
    ]
    return {
        "items": list_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total // page_size + (1 if total % page_size else 0)) if total else 0,
    }
