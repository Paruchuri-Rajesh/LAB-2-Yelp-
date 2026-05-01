"""Review routes — Kafka-first.

Create/update/delete do not write to Mongo directly. Each handler
validates the request, publishes an event on the corresponding topic,
and returns 202 Accepted. The ``review-worker`` service consumes the
events and carries out the writes. This matches the Kafka flow in the
Lab 2 spec (see docs/architecture.md).

List/read endpoints remain synchronous reads from Mongo.
"""
import math

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.kafka_utils import Topics, publish_event
from app.schemas.review import (
    ReviewAccepted, ReviewCreate, ReviewUpdate, ReviewsResponse,
)
from app.services.review_service import (
    assert_user_can_review,
    build_create_payload,
    build_delete_payload,
    build_update_payload,
    enforce_review_owner,
    list_reviews_for_restaurant,
)

router = APIRouter()


@router.get("/{restaurant_id}/reviews", response_model=ReviewsResponse)
async def list_reviews(restaurant_id: str, page: int = 1, page_size: int = 20):
    items, total = await list_reviews_for_restaurant(restaurant_id, page, page_size)
    return ReviewsResponse(
        items=items, total=total, page=page, page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


@router.post(
    "/{restaurant_id}/reviews",
    response_model=ReviewAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_review(restaurant_id: str, data: ReviewCreate, current_user=Depends(get_current_user)):
    await assert_user_can_review(restaurant_id, current_user["id"])
    payload = build_create_payload(restaurant_id, current_user["id"], current_user.get("name"), data)
    await publish_event(Topics.REVIEW_CREATED, payload, key=restaurant_id)
    return ReviewAccepted(message="Review accepted and queued for processing")


@router.put(
    "/{restaurant_id}/reviews/{review_id}",
    response_model=ReviewAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def edit_review(
    restaurant_id: str,
    review_id: str,
    data: ReviewUpdate,
    current_user=Depends(get_current_user),
):
    await enforce_review_owner(review_id, current_user["id"])
    payload = build_update_payload(review_id, current_user["id"], data)
    await publish_event(Topics.REVIEW_UPDATED, payload, key=restaurant_id)
    return ReviewAccepted(message="Review update queued for processing")


@router.delete(
    "/{restaurant_id}/reviews/{review_id}",
    response_model=ReviewAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def remove_review(restaurant_id: str, review_id: str, current_user=Depends(get_current_user)):
    await enforce_review_owner(review_id, current_user["id"])
    payload = build_delete_payload(review_id, current_user["id"], restaurant_id)
    await publish_event(Topics.REVIEW_DELETED, payload, key=restaurant_id)
    return ReviewAccepted(message="Review deletion queued for processing")
