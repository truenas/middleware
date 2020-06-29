"""
Add Rsyncmod enabled field

Revision ID: 71a8d1e504a7
Revises: c01e9d77922e
Create Date: 2020-06-19 16:10:59.501147+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '71a8d1e504a7'
down_revision = 'c01e9d77922e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_rsyncmod', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rsyncmod_enabled', sa.Boolean(), default=True))
