"""Consumes user.* topics and writes activity entries to Mongo."""
import asyncio
import logging
from datetime import datetime

from app.database import get_db, init_indexes
from app.kafka_utils.consumer import run_consumer
from app.kafka_utils.topics import Topics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("user-worker")


async def handle(topic: str, payload: dict) -> None:
    logger.info("recv topic=%s payload_keys=%s", topic, list(payload.keys()))
    await get_db().activity_log.insert_one({
        "type": topic,
        "payload": payload,
        "logged_at": datetime.utcnow(),
    })


async def main() -> None:
    await init_indexes()
    await run_consumer(
        topics=[Topics.USER_CREATED, Topics.USER_UPDATED],
        handler=handle,
        group_id="user-worker",
    )


if __name__ == "__main__":
    asyncio.run(main())
