"""Make x-frame-options configurable

Revision ID: 674afdc2a00b
Revises: 9e5e27934a42
Create Date: 2022-01-07 15:01:54.309469+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '674afdc2a00b'
down_revision = '9e5e27934a42'


def upgrade():
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('stg_guix_frame_options', sa.String(length=120), nullable=False, server_default='SAMEORIGIN')
        )


def downgrade():
    pass
