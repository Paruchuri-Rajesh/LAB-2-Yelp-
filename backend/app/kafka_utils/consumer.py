"""Kafka consumer scaffolding for worker services.

Each worker entrypoint (see ``app/workers/``) calls ``run_consumer`` with a
list of topics and an async handler. The consumer commits offsets after the
handler returns successfully so a crash mid-handler leads to re-delivery
rather than lost events.
"""
import asyncio
import json
import logging
from typing import Awaitable, Callable, Iterable

from aiokafka import AIOKafkaConsumer

from app.config import settings

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict], Awaitable[None]]


async def run_consumer(topics: Iterable[str], handler: Handler, group_id: str | None = None) -> None:
    consumer = AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id or settings.KAFKA_CONSUMER_GROUP,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")) if v else None,
    )
    await consumer.start()
    logger.info("Consumer started on topics=%s group=%s", list(topics), group_id)
    try:
        async for msg in consumer:
            try:
                await handler(msg.topic, msg.value or {})
                await consumer.commit()
            except Exception as exc:
                logger.exception("Handler failed topic=%s offset=%s: %s", msg.topic, msg.offset, exc)
                await asyncio.sleep(1)
    finally:
        await consumer.stop()
