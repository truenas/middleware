"""CPU Pinning

Revision ID: 0267cef97ec3
Revises: 59fbc9897ec3
Create Date: 2022-05-27 12:30:03.593598+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0267cef97ec3'
down_revision = '59fbc9897ec3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vm_vm', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cpuset', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('nodeset', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('pin_vcpus', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    pass
