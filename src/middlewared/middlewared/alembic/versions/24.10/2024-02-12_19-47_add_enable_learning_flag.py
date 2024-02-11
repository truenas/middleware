"""Add enable learning flag

Revision ID: 7836261b2f64
Revises: 968d515e63e7
Create Date: 2024-02-12 19:47:35.379137+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '7836261b2f64'
down_revision = '968d515e63e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('network_bridge', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enable_learning', sa.Boolean(), nullable=False, server_default='1'))


def downgrade():
    pass
