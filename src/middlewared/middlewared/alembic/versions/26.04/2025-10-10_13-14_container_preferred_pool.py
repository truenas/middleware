"""Add preferred_pool to container_config

Revision ID: 809c51228665
Revises: da2c571ee752
Create Date: 2025-10-10 13:14:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '809c51228665'
down_revision = '9ca1e4a9d29b'
branch_labels = None
depends_on = None


def upgrade():
    # Add preferred_pool column to container_config table
    with op.batch_alter_table('container_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preferred_pool', sa.Text(), nullable=True))


def downgrade():
    # Remove preferred_pool column from container_config table
    with op.batch_alter_table('container_config', schema=None) as batch_op:
        batch_op.drop_column('preferred_pool')
