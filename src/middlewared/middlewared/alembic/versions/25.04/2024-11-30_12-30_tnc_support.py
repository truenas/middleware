"""
TNC Support

Revision ID: 83d9689fcbc8
Revises: bb352e66987f
Create Date: 2024-11-30 12:30:41.855489+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '83d9689fcbc8'
down_revision = 'bb352e66987f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'truenas_connect',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.BOOLEAN(), nullable=False),
        sa.Column('claim_token', sa.TEXT(), nullable=True),
        sa.Column('jwt_token', sa.TEXT(), nullable=True),
        sa.Column('claim_token_system_id', sa.String(length=255), nullable=True),
        sa.Column('jwt_token_system_id', sa.String(length=255), nullable=True),
        sa.Column('ip', sa.String(length=255), nullable=True),
        sa.Column('acme_key', sa.TEXT(), nullable=True),
        sa.Column('acme_account_uri', sa.String(length=255), nullable=True),
        sa.Column('acme_directory_uri', sa.String(length=255), nullable=True),
        sa.Column('jwt_details', sa.TEXT(), nullable=False, server_default='{}'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_truenas_connect')),
        sqlite_autoincrement=True,
    )


def downgrade():
    pass