"""FastAPI app: routers under /api and saved photos at /api/files."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, db
from app.api import decisions, floor, tanks


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init_db()
    yield


app = FastAPI(title="Thetis", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

health = APIRouter(prefix="/api")


@health.get("/health")
def get_health() -> dict:
    return {"ok": True}


app.include_router(health)
app.include_router(floor.router)
app.include_router(tanks.router)
app.include_router(decisions.router)

# Only photo folders are public. The database in the same data folder is not.
config.photos_dir().mkdir(parents=True, exist_ok=True)
config.uploads_dir().mkdir(parents=True, exist_ok=True)
app.mount("/api/files/photos", StaticFiles(directory=config.photos_dir(), check_dir=False), name="photos")
app.mount("/api/files/uploads", StaticFiles(directory=config.uploads_dir(), check_dir=False), name="uploads")
