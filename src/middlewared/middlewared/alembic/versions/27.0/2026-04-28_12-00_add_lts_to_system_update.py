"""Add upd_lts column to system_update

Revision ID: e9d4f1a2b3c5
Revises: a3b4c5d6e7f8
Create Date: 2026-04-28 12:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9d4f1a2b3c5'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('system_update', schema=None) as batch_op:
        batch_op.add_column(sa.Column('upd_lts', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('system_update', schema=None) as batch_op:
        batch_op.drop_column('upd_lts')
