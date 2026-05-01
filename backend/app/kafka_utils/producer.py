"""Kafka producer used by API services.

A single ``AIOKafkaProducer`` is shared per process, started during FastAPI
startup and stopped during shutdown. API routes call ``publish_event`` after
writing to Mongo — workers consume the event and carry out side-effects
(rating recalculation, denormalised counters, etc.).

If the broker is unreachable we log and swallow the error so the API does
not fail user requests when Kafka is down. Workers will reconcile state on
the next successful publish.
"""
import json
import logging
from datetime import datetime
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from app.config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


def _default(o: Any):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


async def start_producer() -> None:
    global _producer
    if _producer is not None:
        return
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        client_id=settings.KAFKA_CLIENT_ID,
        value_serializer=lambda v: json.dumps(v, default=_default).encode("utf-8"),
    )
    try:
        await _producer.start()
    except KafkaConnectionError as exc:
        logger.warning("Kafka unavailable at startup: %s", exc)
        _producer = None


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
        finally:
            _producer = None


def get_producer() -> AIOKafkaProducer | None:
    return _producer


async def publish_event(topic: str, payload: dict, key: str | None = None) -> None:
    if _producer is None:
        logger.warning("Producer not started; dropping event topic=%s", topic)
        return
    try:
        k = key.encode("utf-8") if key else None
        await _producer.send_and_wait(topic, payload, key=k)
    except Exception as exc:
        logger.exception("Failed to publish to %s: %s", topic, exc)
