"""Cited question-answering endpoint."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Claim
from app.db.session import get_db
from app.schemas import QARequest, QAResponse
from app.services.qa import answer_question

router = APIRouter(prefix="/claims/{claim_id}/qa", tags=["qa"])


@router.post("", response_model=QAResponse)
def ask(
    claim_id: uuid.UUID,
    payload: QARequest,
    db: Session = Depends(get_db),
) -> QAResponse:
    if db.get(Claim, claim_id) is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return answer_question(
        db=db,
        claim_id=claim_id,
        question=payload.question,
        top_k=payload.top_k,
    )
