"""Add apps metrics server
Revision ID: 9c44b7e06dff
Revises: 2bef686cbf7d
Create Date: 2023-01-20 00:20:00.702138+00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '9c44b7e06dff'
down_revision = '2bef686cbf7d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('metrics_server', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    pass
