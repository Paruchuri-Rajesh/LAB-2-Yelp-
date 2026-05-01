"""Yelp Fusion API client with read-through cache to Mongo.

`search_and_cache` is called from restaurant search; results are upserted
into MongoDB by `yelp_id`. `refresh_one` is called when a single restaurant
detail is requested and its cached copy is older than CACHE_TTL_HOURS.

Owner-managed fields (custom photos, hours) are preserved via `$setOnInsert`
so a refresh from Yelp does not overwrite them.
"""
import logging
import os
from datetime import datetime, timedelta

import httpx

from app.database import get_db

log = logging.getLogger(__name__)

YELP_BASE = "https://api.yelp.com/v3"
CACHE_TTL_HOURS = 24

_PRICE_TO_YELP = {"$": "1", "$$": "2", "$$$": "3", "$$$$": "4"}
_SORT_TO_YELP = {
    "recommended": "best_match",
    "rating": "rating",
    "review_count": "review_count",
}

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient | None:
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("YELP_API_KEY")
    if not api_key:
        return None
    _client = httpx.AsyncClient(
        base_url=YELP_BASE,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=8.0,
    )
    return _client


def yelp_sort(sort_by: str | None) -> str:
    return _SORT_TO_YELP.get(sort_by or "", "best_match")


def yelp_price(price_range: str | None) -> str | None:
    if not price_range:
        return None
    return _PRICE_TO_YELP.get(price_range)


def is_stale(doc: dict, hours: int = CACHE_TTL_HOURS) -> bool:
    last = doc.get("last_fetched_at")
    if not last:
        return True
    return datetime.utcnow() - last > timedelta(hours=hours)


def _build_set_fields(biz: dict) -> dict:
    loc = biz.get("location") or {}
    coords = biz.get("coordinates") or {}
    now = datetime.utcnow()
    return {
        "yelp_id": biz.get("id"),
        "name": biz.get("name"),
        "slug": biz.get("alias"),
        "cuisine_type": ", ".join(c.get("title") for c in (biz.get("categories") or []) if c.get("title")) or None,
        "address": ", ".join(p for p in (loc.get("display_address") or []) if p) or None,
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
        "source": "yelp",
        "last_fetched_at": now,
        "updated_at": now,
    }


def _build_initial_photos(biz: dict) -> list[dict]:
    yelp_photos = list(biz.get("photos") or [])
    if biz.get("image_url"):
        yelp_photos = [biz["image_url"]] + [p for p in yelp_photos if p != biz["image_url"]]
    return [{"file_path": p, "is_primary": i == 0} for i, p in enumerate(yelp_photos) if p]


async def _upsert_business(biz: dict) -> bool:
    yelp_id = biz.get("id")
    if not yelp_id:
        return False
    set_fields = _build_set_fields(biz)
    set_on_insert = {
        "created_at": datetime.utcnow(),
        "photos": _build_initial_photos(biz),
        "hours": [],
    }
    await get_db().restaurants.update_one(
        {"yelp_id": yelp_id},
        {"$set": set_fields, "$setOnInsert": set_on_insert},
        upsert=True,
    )
    return True


async def search_and_cache(
    *,
    term: str | None = None,
    location: str = "San Jose, CA",
    latitude: float | None = None,
    longitude: float | None = None,
    radius_meters: int | None = None,
    categories: str | None = None,
    price: str | None = None,
    sort_by: str = "best_match",
    open_now: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> int:
    """Hit Yelp Fusion /businesses/search and upsert results into Mongo.

    Returns the number of businesses upserted. Returns 0 silently on any error
    so the caller can fall back to whatever's already cached.
    """
    client = _get_client()
    if client is None:
        return 0

    params: dict = {"limit": min(limit, 50), "offset": offset, "sort_by": sort_by}
    if latitude is not None and longitude is not None:
        params["latitude"] = latitude
        params["longitude"] = longitude
        if radius_meters:
            params["radius"] = min(int(radius_meters), 40000)
    else:
        params["location"] = location
    if term:
        params["term"] = term
    if categories:
        params["categories"] = categories.lower().replace(" ", "")
    if price:
        params["price"] = price
    if open_now:
        params["open_now"] = True

    try:
        r = await client.get("/businesses/search", params=params)
        if r.status_code != 200:
            log.warning("Yelp search returned %s: %s", r.status_code, r.text[:200])
            return 0
        data = r.json()
    except Exception as exc:
        log.warning("Yelp search failed: %s", exc)
        return 0

    count = 0
    for biz in data.get("businesses", []):
        if await _upsert_business(biz):
            count += 1
    return count


async def refresh_one(yelp_id: str) -> bool:
    """Fetch a single business detail from Yelp and upsert. Silent on error."""
    client = _get_client()
    if client is None or not yelp_id:
        return False
    try:
        r = await client.get(f"/businesses/{yelp_id}")
        if r.status_code != 200:
            log.warning("Yelp detail %s returned %s", yelp_id, r.status_code)
            return False
        biz = r.json()
    except Exception as exc:
        log.warning("Yelp detail fetch failed for %s: %s", yelp_id, exc)
        return False
    return await _upsert_business(biz)
