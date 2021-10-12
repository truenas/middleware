"""
VM Architecture/Machine type choices

Revision ID: 3a3a37c1f48c
Revises: 4686771af68a
Create Date: 2021-02-08 13:13:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '3a3a37c1f48c'
down_revision = '4686771af68a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('arch_type', sa.String(length=255), nullable=True, default=None))
        batch_op.add_column(sa.Column('machine_type', sa.String(length=255), nullable=True, default=None))


def downgrade():
    pass
