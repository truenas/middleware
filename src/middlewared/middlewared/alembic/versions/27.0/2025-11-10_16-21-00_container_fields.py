"""
Remove unsupported CPU/memory fields from container model

Revision ID: e41efceeeb41
Revises: 6041af215ccd
Create Date: 2025-11-10 16:21:28.600327+00:00
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e41efceeeb41'
down_revision = '6041af215ccd'
branch_labels = None
depends_on = None


def upgrade():
    # Remove vcpus, memory, cores, threads fields
    # These fields were exposed in the API but not properly supported for LXC containers
    # cpuset is kept as it's a valid feature for LXC containers (cgroups cpuset controller)
    with op.batch_alter_table('container_container', schema=None) as batch_op:
        batch_op.drop_column('vcpus')
        batch_op.drop_column('memory')
        batch_op.drop_column('cores')
        batch_op.drop_column('threads')


def downgrade():
    pass
