"""
Add validate host path field

Revision ID: adb5c45a0383
Revises: 32a49386d6c3
Create Date: 2022-07-03 18:10:27.526805+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'adb5c45a0383'
down_revision = '32a49386d6c3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('validate_host_path', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    pass
