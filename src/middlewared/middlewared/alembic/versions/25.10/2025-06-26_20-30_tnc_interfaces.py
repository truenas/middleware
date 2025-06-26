""" Add interfaces and interfaces_ips to truenas_connect

Revision ID: tnc_interfaces_001
Revises:
Create Date: 2025-06-26 20:30:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'tnc_interfaces_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interfaces', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('interfaces_ips', sa.JSON(), nullable=False, server_default='[]'))


def downgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.drop_column('interfaces_ips')
        batch_op.drop_column('interfaces')