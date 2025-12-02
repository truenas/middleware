"""
Move nvidia driver configuration to sys adv

Revision ID: d2c5ab6398b3
Revises: bf646ce959c5
Create Date: 2025-12-02 15:09:18.331279+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'd2c5ab6398b3'
down_revision = 'bf646ce959c5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('storage_volume', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vol_all_sed', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    pass
