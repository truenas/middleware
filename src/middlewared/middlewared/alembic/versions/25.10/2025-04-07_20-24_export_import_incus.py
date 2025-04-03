"""
Export/Import functionality in Incus

Revision ID: 43743e57165d
Revises: d7e3a916db65
Create Date: 2025-04-07 20:24:32.110298+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '43743e57165d'
down_revision = 'd7e3a916db65'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('virt_global', schema=None) as batch_op:
        batch_op.add_column(sa.Column('export_dir', sa.Text(), nullable=True))


def downgrade():
    pass
