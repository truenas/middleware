"""
VM CPU mode/model fields

Revision ID: 3ecb7147c137
Revises: 71a8d1e504a7
Create Date: 2020-07-09 16:11:26.058680+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '3ecb7147c137'
down_revision = '71a8d1e504a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cpu_mode', sa.TEXT(), nullable=True))
        batch_op.add_column(sa.Column('cpu_model', sa.TEXT(), nullable=True))
