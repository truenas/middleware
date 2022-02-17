"""add stp column to bridge table

Revision ID: 7a143979d99b
Revises: cda35deeed4f
Create Date: 2022-02-17 14:24:38.186590+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a143979d99b'
down_revision = 'cda35deeed4f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('network_bridge', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stp', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    with op.batch_alter_table('network_bridge', schema=None) as batch_op:
        batch_op.drop_column('stp')
