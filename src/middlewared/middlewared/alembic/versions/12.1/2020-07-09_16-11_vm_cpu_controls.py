"""
VM CPU mode/model fields

Revision ID: 3ecb7147c137
Revises: 25962b409a1e
Create Date: 2020-07-09 16:11:26.058680+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '3ecb7147c137'
down_revision = '25962b409a1e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cpu_mode', sa.Text(), server_default='CUSTOM', nullable=False))
        batch_op.add_column(sa.Column('cpu_model', sa.TEXT(), nullable=True))
