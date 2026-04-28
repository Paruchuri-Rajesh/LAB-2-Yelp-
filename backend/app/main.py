"""API service entrypoint.

The same codebase runs as four distinct containers — ``user-api``,
``owner-api``, ``restaurant-api`` and ``review-api``. The ``SERVICE_NAME``
environment variable selects which routers are mounted so every container
exposes only the endpoints it owns. ``SERVICE_NAME=all`` keeps the
monolithic behaviour for local dev.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_indexes, close_client
from app.kafka_utils import start_producer, stop_producer


SERVICE_ROUTERS: dict[str, list[str]] = {
    "user-api": ["auth", "users", "preferences"],
    "owner-api": ["owner"],
    "restaurant-api": ["restaurants"],
    "review-api": ["reviews"],
    "ai-api": ["ai_assistant"],
    "all": ["auth", "users", "preferences", "restaurants", "reviews", "owner", "ai_assistant"],
}


def _include_routers(app: FastAPI, names: list[str]) -> None:
    prefix = "/api/v1"
    if "auth" in names:
        from app.routers.auth import router as auth_router
        app.include_router(auth_router, prefix=f"{prefix}/auth", tags=["auth"])
    if "users" in names:
        from app.routers.users import router as users_router
        app.include_router(users_router, prefix=f"{prefix}/users", tags=["users"])
    if "preferences" in names:
        from app.routers.preferences import router as preferences_router
        app.include_router(preferences_router, prefix=f"{prefix}/users", tags=["preferences"])
    if "restaurants" in names:
        from app.routers.restaurants import router as restaurants_router
        app.include_router(restaurants_router, prefix=f"{prefix}/restaurants", tags=["restaurants"])
    if "reviews" in names:
        from app.routers.reviews import router as reviews_router
        app.include_router(reviews_router, prefix=f"{prefix}/restaurants", tags=["reviews"])
    if "owner" in names:
        from app.routers.owner import router as owner_router
        app.include_router(owner_router, prefix=f"{prefix}/owner", tags=["owner"])
    if "ai_assistant" in names:
        from app.routers.ai_assistant import router as ai_assistant_router
        app.include_router(ai_assistant_router, prefix=f"{prefix}/ai-assistant", tags=["ai-assistant"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_indexes()
    await start_producer()
    try:
        yield
    finally:
        await stop_producer()
        await close_client()


def create_app() -> FastAPI:
    service = settings.SERVICE_NAME or "all"
    names = SERVICE_ROUTERS.get(service, SERVICE_ROUTERS["all"])
    app = FastAPI(title=f"Yelp {service}", version="2.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    upload_root = Path(settings.UPLOAD_DIR)
    upload_root.mkdir(parents=True, exist_ok=True)
    (upload_root / "profile_pics").mkdir(exist_ok=True)
    (upload_root / "restaurant_photos").mkdir(exist_ok=True)
    (upload_root / "review_photos").mkdir(exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict:
        return {"status": "ok", "service": service}

    _include_routers(app, names)
    return app


app = create_app()
