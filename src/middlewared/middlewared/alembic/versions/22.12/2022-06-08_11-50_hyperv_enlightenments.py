"""
Hyper-V enlightenments

Revision ID: afa3965ed8fc
Revises: 67d87d9cfc30
Create Date: 2022-06-08 11:50:50.818433+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'afa3965ed8fc'
down_revision = '67d87d9cfc30'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hyperv_enlightenments', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    pass
