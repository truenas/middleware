"""add nfsv4 owner_major column

Revision ID: fee786dfe121
Revises: 45d6f6f07b0f
Create Date: 2021-09-14 19:28:42.914039+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'fee786dfe121'
down_revision = '45d6f6f07b0f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nfs_srv_v4_owner_major', sa.String(length=1023), nullable=True))

    op.execute(text('UPDATE services_nfs SET nfs_srv_v4_owner_major = ""'))

    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        batch_op.alter_column('nfs_srv_v4_owner_major', existing_type=sa.VARCHAR(1023), nullable=False)


def downgrade():
    with op.batch_alter_table('services_nfs', schema=None) as batch_op:
        batch_op.drop_column('nfs_srv_v4_owner_major')
