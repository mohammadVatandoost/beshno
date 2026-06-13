"""add transcript column to podcasts

Stores timestamped transcript cues (karaoke-style audio sync).

Revision ID: c1a4e7b2f8d6
Revises: b7f3c2a1d9e4
Create Date: 2026-06-13 16:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1a4e7b2f8d6"
down_revision: Union[str, None] = "b7f3c2a1d9e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("transcript", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.drop_column("transcript")
