"""Add iSCSI mode

Revision ID: cb58cc72a1d5
Revises: ad6bd79a37d7
Create Date: 2026-03-20 15:53:19.797518+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cb58cc72a1d5'
down_revision = 'ad6bd79a37d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitargetglobalconfiguration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_mode', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('services_iscsitargetglobalconfiguration', schema=None) as batch_op:
        batch_op.drop_column('iscsi_mode')
