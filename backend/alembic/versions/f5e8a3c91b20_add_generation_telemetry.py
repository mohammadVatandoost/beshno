"""add generation telemetry (token usage + timing)

Revision ID: f5e8a3c91b20
Revises: e3c6a8b1f2d7
Create Date: 2026-06-13 17:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5e8a3c91b20"
down_revision: Union[str, None] = "e3c6a8b1f2d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "total_input_tokens",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "total_output_tokens",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("generation_ms", sa.Integer(), nullable=True)
        )

    with op.batch_alter_table("agent_steps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("input_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("output_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_steps", schema=None) as batch_op:
        batch_op.drop_column("output_tokens")
        batch_op.drop_column("input_tokens")

    with op.batch_alter_table("podcasts", schema=None) as batch_op:
        batch_op.drop_column("generation_ms")
        batch_op.drop_column("llm_calls")
        batch_op.drop_column("total_output_tokens")
        batch_op.drop_column("total_input_tokens")
