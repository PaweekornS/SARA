"""
Database Session and Engine Setup
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

# ── Global Variables & Database Engine ───────────────────────────────────────

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


# ── Database Dependency ──────────────────────────────────────────────────────

async def get_db():
    """Dependency for obtaining async DB sessions in FastAPI routers."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()