from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT
from app.config import settings


_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI, uuidRepresentation="standard")
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[settings.MONGO_DB]
    return _db


async def init_indexes() -> None:
    db = get_db()
    await db.users.create_index([("email", ASCENDING)], unique=True)
    await db.users.create_index([("is_active", ASCENDING)])

    await db.sessions.create_index([("jti", ASCENDING)], unique=True)
    await db.sessions.create_index([("user_id", ASCENDING)])
    await db.sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    await db.restaurants.create_index([("name", ASCENDING)])
    await db.restaurants.create_index([("city", ASCENDING)])
    await db.restaurants.create_index([("cuisine_type", ASCENDING)])
    await db.restaurants.create_index([("avg_rating", DESCENDING)])
    await db.restaurants.create_index([("yelp_id", ASCENDING)], unique=True, sparse=True)
    try:
        await db.restaurants.create_index(
            [("name", TEXT), ("description", TEXT), ("cuisine_type", TEXT)],
            name="restaurant_text_idx",
            default_language="english",
        )
    except Exception:
        pass

    await db.reviews.create_index([("restaurant_id", ASCENDING), ("user_id", ASCENDING)], unique=True, sparse=True)
    await db.reviews.create_index([("restaurant_id", ASCENDING), ("created_at", DESCENDING)])
    await db.reviews.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

    await db.favorites.create_index([("user_id", ASCENDING), ("restaurant_id", ASCENDING)], unique=True)
    await db.favorites.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

    await db.ownerships.create_index([("restaurant_id", ASCENDING), ("owner_id", ASCENDING)], unique=True)
    await db.ownerships.create_index([("owner_id", ASCENDING)])

    await db.preferences.create_index([("user_id", ASCENDING)], unique=True)
    await db.restaurant_views.create_index([("restaurant_id", ASCENDING), ("viewed_at", DESCENDING)])


async def close_client() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
