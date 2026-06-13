"""add tone and resolved_tone to podcasts

Revision ID: e3c6a8b1f2d7
Revises: d2b5f9c34a71
Create Date: 2026-06-13 16:10:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3c6a8b1f2d7"
down_revision: Union[str, None] = "d2b5f9c34a71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "tone",
                sa.String(length=20),
                nullable=False,
                server_default="auto",
            )
        )
        batch_op.add_column(
            sa.Column("resolved_tone", sa.String(length=20), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.drop_column("resolved_tone")
        batch_op.drop_column("tone")
