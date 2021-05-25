"""
Remove AAM from disks

Revision ID: bd637e18fb0b
Revises: 45724786402e
Create Date: 2021-05-25 21:32:28.702007+00:00

"""
from alembic import op


revision = 'bd637e18fb0b'
down_revision = '45724786402e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('storage_disk', schema=None) as batch_op:
        batch_op.drop_column('disk_acousticlevel')


def downgrade():
    pass
