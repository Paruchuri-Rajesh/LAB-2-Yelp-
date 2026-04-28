"""Server-side session records backed by MongoDB.

Each successful login inserts a document into ``sessions``. The JWT carries
the session ``jti``; every authenticated request re-reads the doc, so logout
or admin revocation takes effect immediately.

Mongo's TTL index on ``expires_at`` (see ``database.init_indexes``) purges
expired sessions automatically.
"""
from datetime import datetime

from app.database import get_db


async def create_session(user_id: str, jti: str, expires_at: datetime, user_agent: str | None = None) -> None:
    await get_db().sessions.insert_one(
        {
            "jti": jti,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "user_agent": user_agent,
            "revoked": False,
        }
    )


async def session_active(jti: str) -> bool:
    doc = await get_db().sessions.find_one({"jti": jti})
    return bool(doc and not doc.get("revoked"))


async def revoke_session(jti: str) -> None:
    await get_db().sessions.update_one({"jti": jti}, {"$set": {"revoked": True}})


async def revoke_all_for_user(user_id: str) -> None:
    await get_db().sessions.update_many({"user_id": user_id}, {"$set": {"revoked": True}})
