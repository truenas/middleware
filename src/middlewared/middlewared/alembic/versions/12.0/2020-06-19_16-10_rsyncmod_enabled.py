"""
Add Rsyncmod enabled field

Revision ID: 71a8d1e504a7
Revises: 8ac8158773c4
Create Date: 2020-06-19 16:10:59.501147+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '71a8d1e504a7'
down_revision = '8ac8158773c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_rsyncmod', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rsyncmod_enabled', sa.Boolean(), default=True))
