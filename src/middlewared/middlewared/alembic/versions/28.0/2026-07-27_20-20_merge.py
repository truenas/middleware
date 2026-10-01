"""Merge migration for normalizing failover timeout (revision 1dc145b1f6fa)

Revision ID: 74ee5c16e7ff
Revises: f6576b92199e, 1dc145b1f6fa
Create Date: 2026-07-27 20:20:00.000000+00:00

"""

# revision identifiers, used by Alembic.
revision = "74ee5c16e7ff"
down_revision = ("f6576b92199e", "1dc145b1f6fa")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
