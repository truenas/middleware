""" Add use_all_interfaces to truenas_connect

Revision ID: 4f3a2b5c6d7e
Revises: 3693df62fd6f
Create Date: 2025-07-08 23:27:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4f3a2b5c6d7e'
down_revision = '3693df62fd6f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.add_column(sa.Column('use_all_interfaces', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.drop_column('use_all_interfaces')
