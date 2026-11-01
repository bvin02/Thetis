"""FastAPI app: routers under /api and saved photos at /api/files."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI

app = FastAPI(title="Thetis", docs_url="/api/docs", openapi_url="/api/openapi.json")

health = APIRouter(prefix="/api")


@health.get("/health")
def get_health() -> dict:
    return {"ok": True}


app.include_router(health)
