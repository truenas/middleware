"""
App registries support

Revision ID: 799718dc329e
Revises: 899852cb2a92
Create Date: 2025-01-13 20:25:41.855489+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '799718dc329e'
down_revision = '899852cb2a92'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'app_registry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True, default=None),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=False),
        sa.Column('uri', sa.String(length=512), nullable=False, unique=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_app_registry')),
        sqlite_autoincrement=True,
    )


def downgrade():
    pass
