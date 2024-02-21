"""
NVRAM attr in VMs

Revision ID: 5901d065eef9
Revises: 7836261b2f64
Create Date: 2024-02-22 21:51:17.935672+00:00
"""
import sqlalchemy as sa
from alembic import op


revision = '5901d065eef9'
down_revision = '7836261b2f64'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nvram_location', sa.TEXT(), nullable=True))


def downgrade():
    pass
