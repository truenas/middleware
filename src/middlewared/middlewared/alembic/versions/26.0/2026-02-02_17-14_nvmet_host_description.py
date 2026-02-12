"""Add description to NVMet host.

Revision ID: 9202ee4732cf
Revises: ec5dad4625ad
Create Date: 2026-02-02 17:14:14.245560+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9202ee4732cf'
down_revision = 'ec5dad4625ad'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('services_nvmet_host', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nvmet_host_description', sa.String(length=255), nullable=False, server_default=''))


def downgrade():
    with op.batch_alter_table('services_nvmet_host', schema=None) as batch_op:
        batch_op.drop_column('nvmet_host_description')
