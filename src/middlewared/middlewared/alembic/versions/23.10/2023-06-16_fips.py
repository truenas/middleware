"""
FIPS Support

Revision ID: c0b117cde6b8
Revises: 0893833a57be
Create Date: 2023-06-16 22:57:01.757983+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c0b117cde6b8'
down_revision = '0893833a57be'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_security',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enable_fips', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    pass
