"""
Remove unused grubconfig attribute in vm table

Revision ID: 0963604b62f9
Revises: 725b7264abe6
Create Date: 2021-25-08 18:50:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa

from middlewared.utils import osc


revision = '0963604b62f9'
down_revision = '725b7264abe6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.drop_column('grubconfig')


def downgrade():
    pass
