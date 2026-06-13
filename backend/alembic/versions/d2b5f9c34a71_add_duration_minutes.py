"""add duration_minutes to podcasts

User-selected target runtime that drives content/script length.

Revision ID: d2b5f9c34a71
Revises: c1a4e7b2f8d6
Create Date: 2026-06-13 16:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2b5f9c34a71"
down_revision: Union[str, None] = "c1a4e7b2f8d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "duration_minutes",
                sa.Integer(),
                nullable=False,
                server_default="10",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.drop_column("duration_minutes")
