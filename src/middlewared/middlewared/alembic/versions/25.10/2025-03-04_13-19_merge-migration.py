""" Merge migration for adding uid/gid 568 idmap

Revision ID: 616c19f82016
Revises: ed9a781ec0c6, 0257529fa6d5
Create Date: 2025-03-04 13:19:11.534941+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '616c19f82016'
down_revision = ('ed9a781ec0c6', '0257529fa6d5')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
