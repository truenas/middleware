"""
Allow marking all SED based pools in db

Revision ID: d2c5ab6398b3
Revises: 64618eb831b2
Create Date: 2025-12-03 15:09:18.331279+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'd2c5ab6398b3'
down_revision = '64618eb831b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('storage_volume', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vol_all_sed', sa.Boolean(), nullable=True))


def downgrade():
    pass
