from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.models import ExportFormat
from app.schemas.export import ExportCreateRequest, ExportResponse
from app.services import exporter


router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/csv", response_model=ExportResponse, status_code=201)
def create_csv_export(request: ExportCreateRequest, db: Session = Depends(deps.get_db)) -> ExportResponse:
    export = exporter.create_export(db, request.thread_id, ExportFormat.CSV)
    db.commit()
    return ExportResponse.model_validate(export)


@router.post("/json", response_model=ExportResponse, status_code=201)
def create_json_export(request: ExportCreateRequest, db: Session = Depends(deps.get_db)) -> ExportResponse:
    export = exporter.create_export(db, request.thread_id, ExportFormat.JSON)
    db.commit()
    return ExportResponse.model_validate(export)


@router.get("/{export_id}")
def download_export(export_id: int, db: Session = Depends(deps.get_db)) -> Response:
    export = exporter.get_export(db, export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found.")

    media_type = "text/csv" if export.format == ExportFormat.CSV else "application/json"
    return StreamingResponse(
        iter([export.content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{export.filename}"'},
    )
