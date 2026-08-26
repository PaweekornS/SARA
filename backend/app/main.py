"""
SARA Backend API Main Entrypoint (v3.0.0-PROD)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import actions, agenda, auth, meetings, people, public, resolutions, series
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

    logger.info("SARA API พร้อมทำงาน (v3.0.0-PROD)")
    yield
    logger.info("ปิดระบบ")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="3.0.0",
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

# Mount all /api routers
for router in (
    auth.router,
    series.router,
    meetings.router,
    resolutions.router,
    agenda.router,
    actions.router,
    people.router,
    public.router,
):
    app.include_router(router, prefix=settings.API_V1_STR)

# Also mount /v1/public for direct OpenAPI integration (POST /v1/public/summarize)
app.include_router(public.router, prefix="/v1")


# ── Route Handlers ───────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "3.0.0-PROD",
        "llm": f"AI4Thai Pathumma ({settings.PATHUMMA_MODEL_NAME})",
        "asr": f"AI4Thai ASR ({settings.ASR_MODEL})",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
