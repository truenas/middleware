"""empty message

Revision ID: 133f2d9049d2
Revises: c0f121844b00
Create Date: 2020-01-07 11:27:47.818373+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '133f2d9049d2'
down_revision = 'c0f121844b00'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cifs_fsrvp', sa.Boolean(), nullable=True))
        batch_op.drop_index('ix_sharing_cifs_share_cifs_storage_task_id')
        batch_op.drop_column('cifs_storage_task_id')

    op.execute("UPDATE sharing_cifs_share SET cifs_fsrvp = 0")

    with op.batch_alter_table('sharing_cifs_share', schema=None) as batch_op:
        batch_op.alter_column('cifs_fsrvp', nullable=False)
