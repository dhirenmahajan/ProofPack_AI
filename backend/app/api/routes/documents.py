"""Document upload + ingestion endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.models import Claim
from app.db.session import get_db
from app.schemas import DocumentOut, UploadResponse
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/claims/{claim_id}/documents", tags=["documents"])

ALLOWED_SOURCE_TYPES = {
    "policy",
    "invoice",
    "receipt",
    "photo",
    "inspection",
    "permit",
    "voicenote",
    "other",
}


@router.post("", response_model=UploadResponse)
async def upload_document(
    claim_id: uuid.UUID,
    file: UploadFile = File(...),
    source_type: str = Form("other"),
    db: Session = Depends(get_db),
) -> UploadResponse:
    if db.get(Claim, claim_id) is None:
        raise HTTPException(status_code=404, detail="Claim not found")

    if source_type not in ALLOWED_SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"source_type must be one of {sorted(ALLOWED_SOURCE_TYPES)}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    document, chunks_created = ingest_document(
        db=db,
        claim_id=claim_id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        source_type=source_type,
        data=data,
    )
    return UploadResponse(
        document=DocumentOut.model_validate(document),
        chunks_created=chunks_created,
    )
