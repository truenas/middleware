"""
GPU isolation property

Revision ID: 72fc294965d1
Revises: ce614715260a
Create Date: 2020-11-23 04:15:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '72fc294965d1'
down_revision = 'ce614715260a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_isolated_gpu_pci_ids', sa.TEXT(), nullable=True))

    op.execute("UPDATE system_advanced SET adv_isolated_gpu_pci_ids = '[]'")

    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.alter_column('adv_isolated_gpu_pci_ids', existing_type=sa.TEXT(), nullable=False)


def downgrade():
    pass
