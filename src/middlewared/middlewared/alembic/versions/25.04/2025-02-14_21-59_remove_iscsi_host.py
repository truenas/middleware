"""Remove iscsi.host APIs

Revision ID: d93139a68db5
Revises: d908d564231d
Create Date: 2025-02-14 21:59:16.989144+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd93139a68db5'
down_revision = 'd908d564231d'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('services_iscsihosttarget')
    op.drop_table('services_iscsihostiqn')
    op.drop_table('services_iscsihost')


def downgrade():
    pass
