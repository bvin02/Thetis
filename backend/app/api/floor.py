"""GET /api/floor: everything the Floor needs, in one response."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.services.views import build_floor

router = APIRouter(prefix="/api", tags=["floor"])


@router.get("/floor")
def get_floor(session: Session = Depends(get_session)) -> dict:
    return build_floor(session)
