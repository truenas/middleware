"""
Enable/Disable Kdump

Revision ID: 57a7094944d7
Revises: 3ecb7147c137
Create Date: 2020-07-09 16:11:26.058680+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '57a7094944d7'
down_revision = '3ecb7147c137'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adv_kdump_enabled', sa.Boolean(), default=False))
