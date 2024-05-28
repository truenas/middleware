"""
Remove swap configuration from system advanced

Revision ID: 0dc9c3f51393
Revises: 135a7e02cbec
Create Date: 2024-05-13 13:29:06.007342+00:00

"""
from alembic import op


revision = '0dc9c3f51393'
down_revision = '135a7e02cbec'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.drop_column('adv_swapondrive')


def downgrade():
    pass
