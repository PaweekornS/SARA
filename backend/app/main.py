"""
SARA Backend API Main Entrypoint
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import actions, agenda, meetings, people, public, resolutions, series
from app.core.config import settings

# ── Global Variables & Constants ─────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Lifespan & Application Setup ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from sqlalchemy import text
        from app.db.session import engine

        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE meeting ADD COLUMN IF NOT EXISTS summary TEXT;"))
    except Exception as exc:
        logger.warning("DB auto-migration check: %s", exc)

    logger.info("SARA API พร้อมทำงาน")
    yield
    logger.info("ปิดระบบ")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="2.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    series.router,
    meetings.router,
    resolutions.router,
    agenda.router,
    actions.router,
    people.router,
    public.router,
):
    app.include_router(router, prefix=settings.API_V1_STR)


# ── Route Handlers ───────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "2.0.0",
        "llm": f"AI4Thai Pathumma ({settings.PATHUMMA_MODEL_NAME})",
        "asr": f"AI4Thai ASR ({settings.ASR_MODEL})",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
