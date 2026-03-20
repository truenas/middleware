"""Add zfs_tier configuration table

Revision ID: a1b2c3d4e5f6
Revises: ad6bd79a37d7
Create Date: 2026-03-19 00:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'ad6bd79a37d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'zfs_tier',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('max_concurrent_jobs', sa.Integer(), nullable=False, default=2),
        sa.Column('min_available_space', sa.Integer(), nullable=False, default=0),
        sa.Column('special_class_metadata_reserve_pct', sa.Integer(), nullable=False, server_default='25'),
    )
    op.execute("INSERT INTO zfs_tier VALUES (1, 0, 2, 0, 25)")


def downgrade():
    op.drop_table('zfs_tier')
