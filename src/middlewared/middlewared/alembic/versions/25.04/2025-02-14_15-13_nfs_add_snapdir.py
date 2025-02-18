"""Add zfs_snapdir to NFS exports

Revision ID: d908d564231d
Revises: 673dd6925aba
Create Date: 2025-02-14 15:13:59.521506+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd908d564231d'
down_revision = '673dd6925aba'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sharing_nfs_share', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nfs_expose_snapshots', sa.Boolean(), nullable=False, server_default='0'))
