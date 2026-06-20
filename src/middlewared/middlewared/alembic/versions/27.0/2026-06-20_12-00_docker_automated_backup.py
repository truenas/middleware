"""Add automated apps backup-to-pool configuration

Revision ID: c4d5e6f70819
Revises: 4a7e1c9b2f30
Create Date: 2026-06-20 12:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f70819'
down_revision = '4a7e1c9b2f30'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'backup_to_pool_enabled', sa.Boolean(), nullable=False, server_default='0'
        ))
        batch_op.add_column(sa.Column('backup_to_pool_target', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column(
            'backup_to_pool_schedule', sa.TEXT(), nullable=False,
            server_default='{"minute": "0", "hour": "0", "dom": "*", "month": "*", "dow": "7"}'
        ))


def downgrade():
    with op.batch_alter_table('services_docker', schema=None) as batch_op:
        batch_op.drop_column('backup_to_pool_schedule')
        batch_op.drop_column('backup_to_pool_target')
        batch_op.drop_column('backup_to_pool_enabled')
