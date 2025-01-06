"""
Remove unused nfs setting: v3_owner_major.

Revision ID: 9b377a479e7c
Revises: 19cdc9f2d2df
Create Date: 2025-01-06 17:16:21.098401+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b377a479e7c'
down_revision = '19cdc9f2d2df'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        batch_op.drop_column('nfs_srv_v4_owner_major')


def downgrade():
    pass
