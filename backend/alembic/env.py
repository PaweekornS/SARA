"""
Alembic environment — schema ของ v2 เปลี่ยนบ่อย จึงต้องมี migration ไม่ใช่ create_all
(งานล้างหนี้ข้อ 4 ใน §8)

ใช้ engine แบบ sync (psycopg2) ในงาน migration เพราะเรียบง่ายกว่าและไม่ต้องมี event loop
ส่วนแอปจริงยังใช้ asyncpg ตามเดิม
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.session import Base

# โหลด model ทุกตัวเพื่อให้ autogenerate มองเห็น metadata ครบ
import app.db.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


config.set_main_option("sqlalchemy.url", _sync_url())


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
