"""Add apps metrics server

Revision ID: 1896dbab6040
Revises: 60de23d5cd17
Create Date: 2023-01-18 19:02:00.702138+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1896dbab6040'
down_revision = '82ad1e72a7f0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_kubernetes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('metrics_server', sa.Boolean(), server_default='0', nullable=False))


def downgrade():
    pass
