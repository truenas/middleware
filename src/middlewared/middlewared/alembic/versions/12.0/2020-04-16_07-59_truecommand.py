"""
TrueCommand Service Model

Revision ID: 58339783792c
Revises: 171f5b91c36e
Create Date: 2020-04-06 07:59:08.663553+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '58339783792c'
down_revision = '171f5b91c36e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'system_truecommand',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key', sa.TEXT(), nullable=True),
        sa.Column('api_key_state', sa.String(length=128), nullable=True),
        sa.Column('wg_public_key', sa.String(length=255), nullable=True),
        sa.Column('wg_private_key', sa.TEXT(), nullable=True),
        sa.Column('wg_address', sa.String(length=255), nullable=True),
        sa.Column('tc_public_key', sa.String(length=255), nullable=True),
        sa.Column('endpoint', sa.String(length=255), nullable=True),
        sa.Column('remote_address', sa.String(length=255), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_system_truecommand'))
    )


def downgrade():
    pass
