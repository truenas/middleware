"""TrueNAS Connect allowed origins

Revision ID: 3c7d1e9a5b20
Revises: 84556ccb6184
Create Date: 2026-11-10 12:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3c7d1e9a5b20"
down_revision = "84556ccb6184"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("truenas_connect", schema=None) as batch_op:
        batch_op.add_column(sa.Column("allowed_origins", sa.TEXT(), nullable=False, server_default="[]"))


def downgrade():
    with op.batch_alter_table("truenas_connect", schema=None) as batch_op:
        batch_op.drop_column("allowed_origins")
