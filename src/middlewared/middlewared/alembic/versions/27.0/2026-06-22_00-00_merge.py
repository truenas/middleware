"""Merge migration for restricting TOTP interval (revision b3f0a9c41d7e)

Revision ID: c1d2e3f4a5b6
Revises: 4a7e1c9b2f30, b3f0a9c41d7e
Create Date: 2026-06-22 00:00:00.000000+00:00

"""

# revision identifiers, used by Alembic.
revision = "c1d2e3f4a5b6"
down_revision = ("4a7e1c9b2f30", "b3f0a9c41d7e")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
