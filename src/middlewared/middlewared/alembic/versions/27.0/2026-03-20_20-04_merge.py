"""Merge migration for NAS-140388 adding iSCSI mode (revision cb58cc72a1d5).

Revision ID: e854b7d2ae59
Revises: ef6c293fc34f, cb58cc72a1d5
Create Date: 2026-03-20 20:04:11.962684+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e854b7d2ae59'
down_revision = ('ef6c293fc34f', 'cb58cc72a1d5')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
