"""
Remove geli related keys

Revision ID: d2a26c29efca
Revises: 1519ee5b6e29
Create Date: 2023-06-04 00:20:01.757983+00:00

"""
from alembic import op


revision = 'd2a26c29efca'
down_revision = '1519ee5b6e29'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('storage_volume', schema=None) as batch_op:
        batch_op.drop_column('vol_encrypt')
        batch_op.drop_column('vol_encryptkey')

    op.drop_table('storage_encrypteddisk')


def downgrade():
    pass
