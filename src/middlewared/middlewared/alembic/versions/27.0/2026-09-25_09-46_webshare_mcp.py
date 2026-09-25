"""Webshare MCP

Revision ID: 93310886a54c
Revises: 09cc64d01835
Create Date: 2026-09-25 09:46:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "93310886a54c"
down_revision = "09cc64d01835"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("services_webshare", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mcp_enabled", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("mcp_allowed_groups", sa.TEXT(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("mcp_allow_write", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("services_webshare", schema=None) as batch_op:
        batch_op.drop_column("mcp_allow_write")
        batch_op.drop_column("mcp_allowed_groups")
        batch_op.drop_column("mcp_enabled")
