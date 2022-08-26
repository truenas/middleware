"""
Add option to enable pausing vms when taking snapshot

Revision ID: daaf691ed483
Revises: 79942334975f
Create Date: 2022-08-18 07:00:09.81180300:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'daaf691ed483'
down_revision = '79942334975f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('suspend_on_snapshot', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    pass
