"""Dashboard API routes: fleet overview, KPIs, and alerts."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import FleetSummaryOut
from app.db.session import get_db_session
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=FleetSummaryOut)
def get_fleet_summary(
    dataset_id: uuid.UUID | None = None,
    model_version_id: uuid.UUID | None = None,
    db: Session = Depends(get_db_session),
) -> dict[str, Any]:
    return DashboardService.get_fleet_summary(db, dataset_id, model_version_id)
