"""Merge migration

Revision ID: fb5567f445b8
Revises: 1fc32b52c240, 7a8b9c0d1e2f
Create Date: 2025-06-23 16:37:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb5567f445b8'
down_revision = ('1fc32b52c240', '7a8b9c0d1e2f')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
