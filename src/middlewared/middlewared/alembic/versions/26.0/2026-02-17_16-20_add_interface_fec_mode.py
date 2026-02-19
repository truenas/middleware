"""Add FEC mode to network interfaces.

Revision ID: ad6bd79a37d7
Revises: a8f5d9e2c1b7
Create Date: 2026-02-17 16:20:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ad6bd79a37d7'
down_revision = 'a8f5d9e2c1b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.add_column(sa.Column('int_fec_mode', sa.String(length=10), nullable=True))


def downgrade():
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.drop_column('int_fec_mode')
