"""
GRUB linux extra arguments

Revision ID: 9372814239d7
Revises: e6aa9844e0c4
Create Date: 2021-04-27 01:15:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '9372814239d7'
down_revision = 'e6aa9844e0c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('adv_kernel_extra_options', sa.TEXT(), server_default='', nullable=False)
        )


def downgrade():
    pass
