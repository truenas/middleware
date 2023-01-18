""" merge migration

Revision ID: 2bef686cbf7d
Revises: 519c9d598091, f93329091a6f
Create Date: 2023-01-18 18:23:13.684608+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2bef686cbf7d'
down_revision = ('519c9d598091', 'f93329091a6f')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
