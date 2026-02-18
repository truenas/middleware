"""Merge migration for ZFS tiering feature

Revision ID: b7c8d9e0f1a2
Revises: ef6c293fc34f, a1b2c3d4e5f6
Create Date: 2026-03-19 00:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = ('ef6c293fc34f', 'a1b2c3d4e5f6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
