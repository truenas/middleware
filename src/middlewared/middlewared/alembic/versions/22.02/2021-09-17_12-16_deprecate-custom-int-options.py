"""deprecate custom interface options

Revision ID: df19c1a8d4ae
Revises: b55d888749aa
Create Date: 2021-09-17 12:16:21.819535+00:00

"""
from alembic import op

revision = 'df19c1a8d4ae'
down_revision = 'b55d888749aa'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.drop_column('int_options')


def downgrade():
    pass
