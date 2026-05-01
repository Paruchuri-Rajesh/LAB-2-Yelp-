"""Seed the Mongo ``yelp_db`` with restaurants from the bundled JSON.

Run once with ``python seed_mongo.py`` after Mongo is up. Safe to re-run —
each business is upserted on ``yelp_id``.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.database import get_db, init_indexes

DATA_FILE = Path(__file__).parent / "yelp" / "yelp_businesses.json"


def _massage(biz: dict) -> dict:
    now = datetime.utcnow()
    loc = biz.get("location") or {}
    coords = biz.get("coordinates") or {}
    photos = biz.get("photos") or []
    if biz.get("image_url"):
        photos = [biz["image_url"]] + [p for p in photos if p != biz["image_url"]]
    return {
        "yelp_id": biz.get("id"),
        "name": biz.get("name"),
        "slug": biz.get("alias"),
        "cuisine_type": ", ".join([c.get("title") for c in (biz.get("categories") or [])]) or None,
        "description": None,
        "address": ", ".join([p for p in (loc.get("display_address") or []) if p]) or None,
        "city": loc.get("city"),
        "state": loc.get("state"),
        "zip_code": loc.get("zip_code"),
        "country": loc.get("country"),
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
        "phone": biz.get("display_phone") or biz.get("phone"),
        "website": biz.get("url"),
        "image_url": biz.get("image_url"),
        "yelp_url": biz.get("url"),
        "price_range": biz.get("price"),
        "avg_rating": float(biz.get("rating") or 0),
        "review_count": int(biz.get("review_count") or 0),
        "is_closed": bool(biz.get("is_closed")),
        "transactions": ",".join(biz.get("transactions") or []) or None,
        "hours_raw": None,
        "amenities": None,
        "keywords": None,
        "source": "yelp",
        "hours": [],
        "photos": [{"file_path": p, "is_primary": i == 0} for i, p in enumerate(photos) if p],
        "created_at": now,
        "updated_at": now,
    }


async def main() -> None:
    await init_indexes()
    db = get_db()

    if not DATA_FILE.exists():
        print(f"No seed file at {DATA_FILE} — skipping restaurants.")
        return

    with DATA_FILE.open() as fh:
        payload = json.load(fh)
    businesses = payload.get("businesses") if isinstance(payload, dict) else payload
    upserted = 0
    for biz in businesses or []:
        doc = _massage(biz)
        if not doc["yelp_id"]:
            continue
        await db.restaurants.update_one(
            {"yelp_id": doc["yelp_id"]},
            {"$set": doc},
            upsert=True,
        )
        upserted += 1
    print(f"Seeded {upserted} restaurants into {db.name}.restaurants")


if __name__ == "__main__":
    asyncio.run(main())
