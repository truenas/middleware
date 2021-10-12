"""
Add field to configure gpus for k8s

Revision ID: 737912c7a9c1
Revises: bd637e18fb0b
Create Date: 2021-06-10 11:30:28.702007+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '737912c7a9c1'
down_revision = 'bd637e18fb0b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('configure_gpus', sa.Boolean(), default=True, nullable=False))


def downgrade():
    pass
