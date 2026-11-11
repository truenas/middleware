"""Webshare MCP

Revision ID: 93310886a54c
Revises: 09cc64d01835
Create Date: 2026-09-25 09:46:00.000000+00:00

"""

# revision identifiers, used by Alembic.
revision = "93310886a54c"
down_revision = "09cc64d01835"
branch_labels = None
depends_on = None


def upgrade():
    # The 27.0 chain adds the services_webshare MCP columns. This revision stays a no-op so databases already
    # stamped with it keep a valid history and databases that got the columns on 27.0 are not altered twice.
    pass


def downgrade():
    pass
