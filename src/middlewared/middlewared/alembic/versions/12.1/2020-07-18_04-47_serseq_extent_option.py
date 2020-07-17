"""
Add serseq enabled field

Revision ID: 66e27ddf4f32
Revises: 3ecb7147c137
Create Date: 2020-06-19 16:10:59.501147+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '66e27ddf4f32'
down_revision = '3ecb7147c137'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitargetextent', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_target_extent_serseq', sa.Boolean(), default=True))
