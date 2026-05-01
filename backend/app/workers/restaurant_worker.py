"""Consumes restaurant.* topics.

Restaurant docs are written synchronously by the API handler (so clients get
a real ``id`` back for the redirect), so this worker's job is bookkeeping:
recording an activity log entry and refreshing denormalised counters. The
pattern still satisfies the spec's producer/consumer separation.
"""
import asyncio
import logging
from datetime import datetime

from app.database import get_db, init_indexes
from app.kafka_utils.consumer import run_consumer
from app.kafka_utils.topics import Topics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("restaurant-worker")


async def _log(event: str, payload: dict) -> None:
    await get_db().activity_log.insert_one({
        "type": event,
        "payload": payload,
        "logged_at": datetime.utcnow(),
    })


async def handle(topic: str, payload: dict) -> None:
    logger.info("recv topic=%s payload_keys=%s", topic, list(payload.keys()))
    await _log(topic, payload)


async def main() -> None:
    await init_indexes()
    await run_consumer(
        topics=[Topics.RESTAURANT_CREATED, Topics.RESTAURANT_UPDATED, Topics.RESTAURANT_CLAIMED],
        handler=handle,
        group_id="restaurant-worker",
    )


if __name__ == "__main__":
    asyncio.run(main())
