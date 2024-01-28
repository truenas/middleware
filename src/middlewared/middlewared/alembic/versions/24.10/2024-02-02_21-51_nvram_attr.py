"""
NVRAM attr in VMs

Revision ID: 5901d065eef9
Revises: 968d515e63e7
Create Date: 2024-02-02 21:51:17.935672+00:00
"""
import sqlalchemy as sa
from alembic import op


revision = '5901d065eef9'
down_revision = '968d515e63e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nvram_location', sa.TEXT(), nullable=True))


def downgrade():
    pass
