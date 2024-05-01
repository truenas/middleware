"""Add iSCSI target options

Revision ID: fc912643baa2
Revises: 4f11cc19bb9c
Create Date: 2024-04-25 19:46:37.356476+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fc912643baa2'
down_revision = '4f11cc19bb9c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitarget', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_target_options', sa.TEXT(), nullable=True))


def downgrade():
    with op.batch_alter_table('services_iscsitarget', schema=None) as batch_op:
        batch_op.drop_column('iscsi_target_options')
