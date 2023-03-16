""" Merge migration for netbiosname change

Revision ID: 7310292225d3
Revises: 1c060aa856ca, 3df90537bffa
Create Date: 2023-03-16 14:41:49.067099+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7310292225d3'
down_revision = ('1c060aa856ca', '3df90537bffa')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
