"""Seed Mongo ``yelp_db.reviews`` from ``yelp/yelp_reviews.json``.

Reviews in the fixture are keyed by an integer ``business_id`` that does not
match real Yelp ids. We round-robin-assign each review to one of the businesses
currently in Mongo (i.e. fetched from the Yelp Fusion API by ``fetch_yelp.py``
+ seeded by ``seed_mongo.py``), then insert with ``user_id`` omitted so the
sparse unique index on ``(restaurant_id, user_id)`` permits multiple seeded
reviews per restaurant.

Run after ``seed_mongo.py``.
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path

from app.database import get_db, init_indexes

DATA_FILE = Path(__file__).parent / "yelp" / "yelp_reviews.json"


async def main() -> None:
    await init_indexes()
    db = get_db()

    if not DATA_FILE.exists():
        print(f"No review fixture at {DATA_FILE} — skipping reviews.")
        return

    restaurants = [
        r async for r in db.restaurants.find({}, {"_id": 1, "name": 1}).sort("_id", 1)
    ]
    if not restaurants:
        print("No restaurants in Mongo — run fetch_yelp.py + seed_mongo.py first.")
        return

    with DATA_FILE.open() as fh:
        reviews = json.load(fh)
    if not isinstance(reviews, list):
        reviews = reviews.get("reviews") or []

    await db.reviews.delete_many({"source": "seed"})

    now = datetime.utcnow()
    docs = []
    for i, rev in enumerate(reviews):
        target = restaurants[i % len(restaurants)]
        rest_id = str(target["_id"])
        try:
            visited = datetime.strptime(rev.get("review_date", ""), "%Y-%m-%d") if rev.get("review_date") else None
        except ValueError:
            visited = None
        docs.append({
            "restaurant_id": rest_id,
            "source": "seed",
            "rating": int(rev.get("rating") or 0),
            "title": None,
            "body": rev.get("review_text"),
            "author_name": rev.get("author"),
            "author_image_url": None,
            "source_url": None,
            "visited_at": visited,
            "useful_votes": int(rev.get("useful_votes") or 0),
            "funny_votes": int(rev.get("funny_votes") or 0),
            "cool_votes": int(rev.get("cool_votes") or 0),
            "created_at": now,
            "updated_at": now,
        })

    if not docs:
        print("No reviews to seed.")
        return

    result = await db.reviews.insert_many(docs, ordered=False)
    print(f"Inserted {len(result.inserted_ids)} reviews across {len(restaurants)} restaurants")

    from app.services.restaurant_service import recalculate_restaurant_ratings
    for r in restaurants:
        await recalculate_restaurant_ratings(str(r["_id"]))
    print(f"Recalculated rating aggregates for {len(restaurants)} restaurants")


if __name__ == "__main__":
    asyncio.run(main())
