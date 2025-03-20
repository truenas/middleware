"""Merge migration for incus storage pools

Revision ID: a34e4c124c25
Revises: 801eb4df44ce, df0bffcf1595
Create Date: 2025-03-13 20:14:54.188759+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a34e4c124c25'
down_revision = ('801eb4df44ce', 'df0bffcf1595')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
