"""VM suspend_on_snapshot default to true

Revision ID: 7d3a1f9c2e84
Revises: a1b2c3d4e5f6
Create Date: 2026-06-08 12:30:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7d3a1f9c2e84"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("vm_vm", schema=None) as batch_op:
        batch_op.alter_column(
            "suspend_on_snapshot",
            existing_type=sa.Boolean(),
            server_default="1",
            existing_nullable=False,
        )
    op.execute("UPDATE vm_vm SET suspend_on_snapshot = 1")
