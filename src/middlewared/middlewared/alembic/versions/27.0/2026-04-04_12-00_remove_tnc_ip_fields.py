"""Remove ips, interfaces, interfaces_ips, use_all_interfaces from truenas_connect.

TrueNAS Connect now derives IPs from system.general.config (ui_address / ui_v6address)
instead of maintaining its own IP configuration.

Revision ID: 8bf95889effa
Revises: 774c3c7cb4ad
Create Date: 2026-04-04 12:00:00.000000+00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '8bf95889effa'
down_revision = '774c3c7cb4ad'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.drop_column('ips')
        batch_op.drop_column('interfaces')
        batch_op.drop_column('interfaces_ips')
        batch_op.drop_column('use_all_interfaces')


def downgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ips', sa.Text(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('interfaces', sa.Text(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('interfaces_ips', sa.Text(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('use_all_interfaces', sa.Boolean(), nullable=False, server_default='1'))
