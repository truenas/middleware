"""Add secure boot column if missing

Revision ID: c8f3a2b4d5e6
Revises: 2368b4b28a87
Create Date: 2025-07-02 10:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError


# revision identifiers, used by Alembic.
revision = 'c8f3a2b4d5e6'
down_revision = '2368b4b28a87'
branch_labels = None
depends_on = None


def upgrade():
    # In 25.10, VM tables were dropped and recreated. The recreate_vm_tables migration
    # doesn't include the enable_secure_boot column, so we need to add it here.
    # This migration also handles the case where the column might already exist
    # (e.g., if the 25.04 migration ran successfully before upgrading to 25.10).
    try:
        with op.batch_alter_table('vm_vm', schema=None) as batch_op:
            batch_op.add_column(sa.Column('enable_secure_boot', sa.Boolean(), nullable=False, server_default='0'))
    except OperationalError:
        # Column might already exist from the 25.04 migration
        pass


def downgrade():
    # We don't remove the column on downgrade to maintain compatibility
    pass
