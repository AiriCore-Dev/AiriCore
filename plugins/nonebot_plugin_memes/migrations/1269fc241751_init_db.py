
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1269fc241751"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("nonebot_plugin_memes_v2",)
depends_on: str | Sequence[str] | None = "14175fde8186"


def upgrade(name: str = "") -> None:
    if name:
        return
    op.create_table(
        "nonebot_plugin_memes_memegenerationrecord_v2",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_persist_id", sa.Integer(), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.Column("meme_key", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint(
            "id", name=op.f("pk_nonebot_plugin_memes_memegenerationrecord_v2")
        ),
        info={"bind_key": "nonebot_plugin_memes"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return
    op.drop_table("nonebot_plugin_memes_memegenerationrecord_v2")
