"""Add NFS RDMA configuration setting

Revision ID: 85e5d349cdb1
Revises: 5fe28eada969
Create Date: 2024-10-04 18:09:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '85e5d349cdb1'
down_revision = '5fe28eada969'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nfs_srv_rdma', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    pass
