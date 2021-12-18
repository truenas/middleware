"""
VM Video Device

Revision ID: 4686771af68a
Revises: 1857e74d5f11
Create Date: 2021-02-08 13:13:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '4686771af68a'
down_revision = '1857e74d5f11'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ensure_display_device', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    pass
