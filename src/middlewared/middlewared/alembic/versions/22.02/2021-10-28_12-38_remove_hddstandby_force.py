"""remove hddstandby_force

Revision ID: 1bdeea0afa8a
Revises: 2076c53a1a28
Create Date: 2021-10-28 12:38:33.398084+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1bdeea0afa8a'
down_revision = '2076c53a1a28'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('storage_disk', schema=None) as batch_op:
        batch_op.drop_column('disk_hddstandby_force')


def downgrade():
    pass
