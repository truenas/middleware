"""Add dedicated_nic to nvmet port config

This will be used with SPDK.

Revision ID: 72b63cd393d3
Revises: 3d738dbd75ef
Create Date: 2025-07-16 16:23:12.160536+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '72b63cd393d3'
down_revision = '3d738dbd75ef'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_nvmet_port', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nvmet_port_dedicated_nic', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('services_nvmet_port', schema=None) as batch_op:
        batch_op.drop_column('nvmet_port_dedicated_nic')
