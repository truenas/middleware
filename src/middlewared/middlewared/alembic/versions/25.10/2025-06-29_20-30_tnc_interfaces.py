""" Add interfaces and interfaces_ips to truenas_connect

Revision ID: 2368b4b28a87
Revises: d4e0268ca57d
Create Date: 2025-06-29 20:30:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2368b4b28a87'
down_revision = 'd4e0268ca57d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.add_column(sa.Column('interfaces', sa.TEXT(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('interfaces_ips', sa.TEXT(), nullable=False, server_default='[]'))


def downgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.drop_column('interfaces_ips')
        batch_op.drop_column('interfaces')
