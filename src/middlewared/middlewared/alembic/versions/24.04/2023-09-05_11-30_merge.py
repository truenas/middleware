"""merge migration

Revision ID: 50873c0db61b
Revises: 80c01d290a1d, 22a23dafd7de
Create Date: 2023-09-05 11:30:59.733983+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '50873c0db61b'
down_revision = ('80c01d290a1d', '22a23dafd7de')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
