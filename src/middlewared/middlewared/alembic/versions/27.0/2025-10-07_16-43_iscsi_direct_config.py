"""Add iscsi_direct_config

Revision ID: 9ca1e4a9d29b
Revises: 1da926419a89
Create Date: 2025-10-07 16:43:35.525174+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ca1e4a9d29b'
down_revision = '1da926419a89'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitargetglobalconfiguration', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_direct_config', sa.Boolean(), nullable=True))


def downgrade():
    with op.batch_alter_table('services_iscsitargetglobalconfiguration', schema=None) as batch_op:
        batch_op.drop_column('iscsi_direct_config')
