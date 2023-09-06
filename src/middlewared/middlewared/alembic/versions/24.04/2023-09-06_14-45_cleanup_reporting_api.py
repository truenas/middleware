"""
Cleanup Reporting API

Revision ID: e915a3b8fff6
Revises: 3f39fe7d911d
Create Date: 2023-09-06 14:45:13.261715+00:00

"""
from alembic import op


revision = 'e915a3b8fff6'
down_revision = '3f39fe7d911d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_reporting', schema=None) as batch_op:
        batch_op.drop_column('graph_age')
        batch_op.drop_column('graph_points')


def downgrade():
    pass
