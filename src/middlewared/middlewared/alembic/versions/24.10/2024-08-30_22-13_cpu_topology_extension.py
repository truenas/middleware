"""
Providing cpu topology extension to VMs

Revision ID: d24d6760fda4
Revises: 7b13df980355
Create Date: 2024-08-30 22:13:09.525439+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'd24d6760fda4'
down_revision = '7b13df980355'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('enable_cpu_topology_extension', sa.Boolean(), nullable=False, server_default='0')
        )


def downgrade():
    pass
