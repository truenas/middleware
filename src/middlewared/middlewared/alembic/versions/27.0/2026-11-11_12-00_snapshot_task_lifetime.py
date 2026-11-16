"""Clamp periodic snapshot task lifetime to at least 1
Revision ID: 6d08137a3def
Revises: b4fac2fc788a
Create Date: 2026-11-11 12:00:00.000000+00:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "6d08137a3def"
down_revision = "b4fac2fc788a"
branch_labels = None
depends_on = None


def upgrade():
    # The API accepted a lifetime of 0 until NAS-142610, which made the entry model reject it on every query.
    op.execute("UPDATE storage_task SET task_lifetime_value = 1 WHERE task_lifetime_value < 1")


def downgrade():
    pass
