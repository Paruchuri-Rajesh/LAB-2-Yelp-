"""Fetch real businesses from the Yelp Fusion API into ``yelp/yelp_businesses.json``.

Run once before ``seed_mongo.py``. Re-running overwrites the JSON, but a
``.bak`` of the previous file is kept so the bundled fixture is not lost.

Env vars (read from ``backend/.env``):
    YELP_API_KEY   required
    YELP_TERM      default "restaurants"
    YELP_LOCATION  default "San Jose, CA"
    YELP_LIMIT     default 200 (capped at 1000 by Yelp)
"""
import json
import os
import sys
from pathlib import Path

import httpx

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

YELP_URL = "https://api.yelp.com/v3/businesses/search"
PAGE_SIZE = 50
HARD_CAP = 1000

OUT_FILE = Path(__file__).parent / "yelp" / "yelp_businesses.json"


def main() -> int:
    api_key = os.environ.get("YELP_API_KEY")
    if not api_key:
        print("ERROR: YELP_API_KEY not set (check backend/.env)", file=sys.stderr)
        return 1

    term = os.environ.get("YELP_TERM", "restaurants")
    location = os.environ.get("YELP_LOCATION", "San Jose, CA")
    target = min(int(os.environ.get("YELP_LIMIT", "200")), HARD_CAP)

    headers = {"Authorization": f"Bearer {api_key}"}
    businesses: list[dict] = []
    seen_ids: set[str] = set()

    with httpx.Client(timeout=20.0) as client:
        for offset in range(0, target, PAGE_SIZE):
            params = {
                "term": term,
                "location": location,
                "limit": min(PAGE_SIZE, target - offset),
                "offset": offset,
            }
            r = client.get(YELP_URL, headers=headers, params=params)
            if r.status_code != 200:
                print(f"ERROR: Yelp returned {r.status_code}: {r.text}", file=sys.stderr)
                return 2
            chunk = r.json().get("businesses") or []
            new = [b for b in chunk if b.get("id") and b["id"] not in seen_ids]
            for b in new:
                seen_ids.add(b["id"])
            businesses.extend(new)
            print(f"  offset={offset:4d}  +{len(new)} businesses (total {len(businesses)})")
            if len(chunk) < PAGE_SIZE:
                break

    if not businesses:
        print("ERROR: no businesses returned — refusing to overwrite existing file.", file=sys.stderr)
        return 3

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if OUT_FILE.exists():
        bak = OUT_FILE.with_suffix(OUT_FILE.suffix + ".bak")
        if not bak.exists():
            OUT_FILE.rename(bak)
            print(f"Backed up previous fixture → {bak.name}")
        else:
            OUT_FILE.unlink()
    OUT_FILE.write_text(json.dumps({"businesses": businesses}, indent=2))
    print(f"Wrote {len(businesses)} businesses → {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
