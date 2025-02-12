"""Add iSER configuration setting

Revision ID: 673dd6925aba
Revises: 287d5bdee5c5
Create Date: 2025-02-11 22:45:50.021091+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '673dd6925aba'
down_revision = '287d5bdee5c5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitargetglobalconfiguration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_iser', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    pass
