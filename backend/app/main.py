"""FastAPI application entrypoint for ProofPack AI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import claims, documents, health, packets, qa
from app.config import settings
from app.db import models  # noqa: F401 - ensure models register on Base
from app.db.session import Base, engine

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("proofpack")


def _init_db() -> None:
    """Ensure extensions, tables, and performance indexes exist (idempotent).

    This is the dev bootstrap. In production the same shape is produced by the
    Alembic baseline migration (`alembic upgrade head`).
    """
    from app.db.indexes import apply_indexes

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        apply_indexes(conn)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _init_db()
        logger.info("Database initialized")
    except Exception as exc:  # noqa: BLE001 - surface clearly, keep app importable
        logger.error("DB init failed: %s", exc)
    yield


app = FastAPI(
    title="ProofPack AI",
    description="Multimodal Disaster Claim Intelligence Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(claims.router)
app.include_router(documents.router)
app.include_router(qa.router)
app.include_router(packets.router)


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": "ProofPack AI",
        "docs": "/docs",
        "health": "/health",
        "providers": "/providers",
    }
