"""remove disable_offload_capabilities column

Revision ID: cda35deeed4f
Revises: 8f72494885e6
Create Date: 2022-02-15 20:08:46.180173+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'cda35deeed4f'
down_revision = '8f72494885e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.drop_column('int_disable_offload_capabilities')


def downgrade():
    pass
