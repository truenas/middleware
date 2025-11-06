"""
Add sed column to disks

Revision ID: ff14ac328c3f
Revises: 32ef531bba38
Create Date: 2025-11-06 11:05:35.525174+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ff14ac328c3f'
down_revision = '32ef531bba38'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('storage_disk', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disk_sed', sa.Boolean(), nullable=True))


def downgrade():
    pass
