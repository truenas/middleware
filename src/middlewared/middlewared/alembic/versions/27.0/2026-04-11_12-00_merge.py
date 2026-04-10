"""Merge migration for NAS-140050 remove TNC IP fields (revision 8bf95889effa).

Revision ID: a3b4c5d6e7f8
Revises: 774c3c7cb4ad, 8bf95889effa
Create Date: 2026-04-11 00:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b4c5d6e7f8'
down_revision = ('774c3c7cb4ad', '8bf95889effa')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
