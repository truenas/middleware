"""Remove legacy UI field

Revision ID: 7f8be1364037
Revises: a87f7ecc4e88
Create Date: 2019-10-30 16:04:12.138197+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '7f8be1364037'
down_revision = 'a87f7ecc4e88'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_advanced', schema=None) as batch_op:
        batch_op.drop_column('adv_legacy_ui')


def downgrade():
    pass
