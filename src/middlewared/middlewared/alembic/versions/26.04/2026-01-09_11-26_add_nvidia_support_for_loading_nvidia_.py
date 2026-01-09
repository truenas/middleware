"""Add NVIDIA persistence mode setting to system advanced

Revision ID: 39799bf97750
Revises: ec5dad4625ad
Create Date: 2026-01-09 11:26:48.584087+00:00

"""
from alembic import op
import sqlalchemy as sa



revision = '39799bf97750'
down_revision = 'ec5dad4625ad'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_nvidia_persistence_mode', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.drop_column('adv_nvidia_persistence_mode')
