"""Add incus storage pools

Revision ID: df0bffcf1595
Revises: 0257529fa6d5
Create Date: 2025-03-07 13:40:53.611152+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df0bffcf1595'
down_revision = '0257529fa6d5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('virt_global', schema=None) as batch_op:
        batch_op.add_column(sa.Column('storage_pools', sa.Text(), nullable=True))
