"""
TNC Configurable Endpoints

Revision ID: af75faf3a0e2
Revises: 799718dc329e
Create Date: 2025-01-14 15:17:35.553785+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'af75faf3a0e2'
down_revision = '799718dc329e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'account_service_base_url', sa.String(length=255), nullable=False,
            server_default='https://account-service.dev.ixsystems.net/'
        ))
        batch_op.add_column(sa.Column(
            'leca_service_base_url', sa.String(length=255), nullable=False,
            server_default='https://leca-server.dev.ixsystems.net/'
        ))
        batch_op.add_column(sa.Column(
            'tnc_base_url', sa.String(length=255), nullable=False,
            server_default='https://truenas.connect.dev.ixsystems.net/'
        ))


def downgrade():
    pass
