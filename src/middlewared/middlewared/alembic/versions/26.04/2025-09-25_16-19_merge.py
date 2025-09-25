"""
Merge migration

Revision ID: da2c571ee752
Revises: 5d51d6e50ff2, 53193fbee3ee
Create Date: 2025-09-25 16:19:11.534941+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da2c571ee752'
down_revision = ('5d51d6e50ff2', '53193fbee3ee')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
