"""Add iSCSI Product ID field

Revision ID: 3298b9ae612b
Revises: fe655f29b9c9
Create Date: 2025-07-23 16:49:05.911976+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3298b9ae612b'
down_revision = 'fe655f29b9c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_iscsitargetextent', schema=None) as batch_op:
        batch_op.add_column(sa.Column('iscsi_target_extent_product_id', sa.Text(), nullable=True))


def downgrade():
    pass
