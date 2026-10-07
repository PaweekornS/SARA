"""
SARA Backend API Main Entrypoint
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import action_items, auth, collections, meetings, public
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="4.0.0",
    root_path=settings.ROOT_PATH,
    docs_url=None if settings.is_prod else "/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

for router in (auth.router, collections.router, meetings.router, action_items.router, public.router):
    app.include_router(router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "4.0.0"}
