"""Webshare readonly

Revision ID: 2f08b4c7a1d9
Revises: d5e404a65f70
Create Date: 2026-10-20 11:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2f08b4c7a1d9"
down_revision = "d5e404a65f70"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sharing_webshare_share", schema=None) as batch_op:
        batch_op.add_column(sa.Column("readonly", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("sharing_webshare_share", schema=None) as batch_op:
        batch_op.drop_column("readonly")
