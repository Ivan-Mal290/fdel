"""share modes for files

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column("share_mode", sa.String(length=16), server_default="link", nullable=False),
    )
    op.add_column("files", sa.Column("access_code", sa.String(length=8), nullable=True))
    op.add_column("files", sa.Column("access_password_hash", sa.String(length=255), nullable=True))
    op.create_index("ix_files_access_code", "files", ["access_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_files_access_code", table_name="files")
    op.drop_column("files", "access_password_hash")
    op.drop_column("files", "access_code")
    op.drop_column("files", "share_mode")
