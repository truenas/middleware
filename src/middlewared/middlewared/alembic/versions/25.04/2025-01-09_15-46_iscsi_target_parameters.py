"""iSCSI target parameters

Revision ID: 899852cb2a92
Revises: 83d9689fcbc8
Create Date: 2025-01-09 15:46:35.550172+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '899852cb2a92'
down_revision = '83d9689fcbc8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitarget', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_target_iscsi_parameters', sa.TEXT(), nullable=True))

def downgrade():
    with op.batch_alter_table('services_iscsitarget', schema=None) as batch_op:
        batch_op.drop_column('iscsi_target_iscsi_parameters')
