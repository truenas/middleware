"""
TNC Heartbeat

Revision ID: 287d5bdee5c5
Revises: af75faf3a0e2
Create Date: 2025-01-16 22:00:35.553785+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '287d5bdee5c5'
down_revision = 'af75faf3a0e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'heartbeat_url', sa.String(length=255), nullable=False,
            server_default='https://heartbeat-service.dev.ixsystems.net/'
        ))
        batch_op.add_column(sa.Column('last_heartbeat_failure_datetime', sa.String(length=255), nullable=True))


def downgrade():
    pass
