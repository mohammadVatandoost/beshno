"""add user_learned_vocabulary

Revision ID: b7f3c2a1d9e4
Revises: 52d01d22f7e8
Create Date: 2026-06-13 15:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f3c2a1d9e4"
down_revision: Union[str, None] = "52d01d22f7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_learned_vocabulary",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=False),
        sa.Column("target_language", sa.String(length=64), nullable=False),
        sa.Column("term", sa.String(length=255), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=True),
        sa.Column("podcast_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner",
            "target_language",
            "term",
            name="uq_learned_vocab_owner_lang_term",
        ),
    )
    with op.batch_alter_table("user_learned_vocabulary", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_user_learned_vocabulary_owner"), ["owner"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_user_learned_vocabulary_target_language"),
            ["target_language"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("user_learned_vocabulary", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_learned_vocabulary_target_language"))
        batch_op.drop_index(batch_op.f("ix_user_learned_vocabulary_owner"))
    op.drop_table("user_learned_vocabulary")
