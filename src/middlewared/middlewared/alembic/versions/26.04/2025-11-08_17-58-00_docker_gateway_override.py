"""
Docker gateway override

Revision ID: 9a162918f752
Revises: 6041af215ccd
Create Date: 2025-11-08 17:58:28.600327+00:00
"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a162918f752'
down_revision = '6041af215ccd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ipv4gateway', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('ipv6gateway', sa.String(length=128), nullable=True))


def downgrade():
    pass
