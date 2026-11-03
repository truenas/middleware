"""Webshare MCP

Revision ID: b4fac2fc788a
Revises: b37fe56131ac
Create Date: 2026-11-03 14:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b4fac2fc788a"
down_revision = "b37fe56131ac"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    # A newer release adds these columns in its own revision; databases that already ran it keep their values.
    if "mcp_enabled" in {column["name"] for column in sa.inspect(conn).get_columns("services_webshare")}:
        return

    with op.batch_alter_table("services_webshare", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mcp_enabled", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("mcp_allowed_groups", sa.TEXT(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("mcp_allow_write", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    pass
