"""Merge migration for NAS-140493 container name sanitization (revision c7d8e9f0a1b2).

Revision ID: 774c3c7cb4ad
Revises: e854b7d2ae59, c7d8e9f0a1b2
Create Date: 2026-04-02 00:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '774c3c7cb4ad'
down_revision = ('e854b7d2ae59', 'c7d8e9f0a1b2')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
