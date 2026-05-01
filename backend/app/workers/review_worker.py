"""Consumes review.* topics and persists reviews to Mongo.

Run as a standalone container. Each message is acknowledged only after the
handler completes, so a crash mid-handler triggers a redelivery.
"""
import asyncio
import logging

from app.database import init_indexes
from app.kafka_utils.consumer import run_consumer
from app.kafka_utils.topics import Topics
from app.services.review_service import apply_created, apply_updated, apply_deleted

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("review-worker")


async def handle(topic: str, payload: dict) -> None:
    logger.info("recv topic=%s payload_keys=%s", topic, list(payload.keys()))
    if topic == Topics.REVIEW_CREATED:
        await apply_created(payload)
    elif topic == Topics.REVIEW_UPDATED:
        await apply_updated(payload)
    elif topic == Topics.REVIEW_DELETED:
        await apply_deleted(payload)


async def main() -> None:
    await init_indexes()
    await run_consumer(
        topics=[Topics.REVIEW_CREATED, Topics.REVIEW_UPDATED, Topics.REVIEW_DELETED],
        handler=handle,
        group_id="review-worker",
    )


if __name__ == "__main__":
    asyncio.run(main())
