"""remove freebsd multipath code

Revision ID: 2c92fe98fc9d
Revises: 1bdeea0afa8a
Create Date: 2021-10-28 16:28:38.775464+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c92fe98fc9d'
down_revision = '1bdeea0afa8a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('storage_disk', schema=None) as batch_op:
        batch_op.drop_column('disk_multipath_name')
        batch_op.drop_column('disk_multipath_member')


def downgrade():
    pass
