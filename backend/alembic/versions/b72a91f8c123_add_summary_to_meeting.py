"""add summary to meeting

Revision ID: b72a91f8c123
Revises: 907976775cac
Create Date: 2026-08-17 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b72a91f8c123'
down_revision: Union[str, None] = '907976775cac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE meeting ADD COLUMN IF NOT EXISTS summary TEXT")


def downgrade() -> None:
    op.drop_column('meeting', 'summary')
