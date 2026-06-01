"""Claim CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Claim, Document
from app.db.session import get_db
from app.schemas import ClaimCreate, ClaimOut, DocumentOut

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def create_claim(payload: ClaimCreate, db: Session = Depends(get_db)) -> Claim:
    claim = Claim(**payload.model_dump())
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


@router.get("", response_model=list[ClaimOut])
def list_claims(db: Session = Depends(get_db)) -> list[Claim]:
    return list(db.execute(select(Claim).order_by(Claim.created_at.desc())).scalars())


def _get_claim_or_404(db: Session, claim_id: uuid.UUID) -> Claim:
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: uuid.UUID, db: Session = Depends(get_db)) -> Claim:
    return _get_claim_or_404(db, claim_id)


@router.get("/{claim_id}/documents", response_model=list[DocumentOut])
def list_claim_documents(
    claim_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[Document]:
    _get_claim_or_404(db, claim_id)
    stmt = (
        select(Document)
        .where(Document.claim_id == claim_id)
        .order_by(Document.created_at.desc())
    )
    return list(db.execute(stmt).scalars())
