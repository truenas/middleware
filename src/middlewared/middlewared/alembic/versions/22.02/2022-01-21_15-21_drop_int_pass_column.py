"""remove int_pass column

Revision ID: 184b771fb710
Revises: b140ab0d3066
Create Date: 2022-01-21 15:21:06.477673+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '184b771fb710'
down_revision = 'b140ab0d3066'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('network_interfaces', schema=None) as batch_op:
        batch_op.drop_column('int_pass')


def downgrade():
    pass
