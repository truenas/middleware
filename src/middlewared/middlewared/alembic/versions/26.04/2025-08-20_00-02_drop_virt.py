"""
Remove Virt plugin

Revision ID: 0716c1a845e2
Revises: 7767afd88989
Create Date: 2025-08-20 00:02:41.855489+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '0716c1a845e2'
down_revision = '7767afd88989'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('virt_global')


def downgrade():
    pass
