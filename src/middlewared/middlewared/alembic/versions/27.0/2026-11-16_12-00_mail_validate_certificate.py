"""Mail certificate validation

Revision ID: b4ada61420a1
Revises: 6d08137a3def
Create Date: 2026-11-16 12:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b4ada61420a1"
down_revision = "6d08137a3def"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("system_email", schema=None) as batch_op:
        batch_op.add_column(sa.Column("em_validate_certificate", sa.Boolean(), nullable=False, server_default="1"))


def downgrade():
    pass
