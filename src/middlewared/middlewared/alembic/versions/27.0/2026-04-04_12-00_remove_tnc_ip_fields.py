"""Remove ips, interfaces, interfaces_ips, use_all_interfaces from truenas_connect.

TrueNAS Connect now derives IPs from system.general.config (ui_address / ui_v6address)
instead of maintaining its own IP configuration.

Revision ID: 8bf95889effa
Revises: c7d8e9f0a1b2
Create Date: 2026-04-04 12:00:00.000000+00:00

"""
from alembic import op


revision = '8bf95889effa'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('truenas_connect', schema=None) as batch_op:
        batch_op.drop_column('ips')
        batch_op.drop_column('interfaces')
        batch_op.drop_column('interfaces_ips')
        batch_op.drop_column('use_all_interfaces')


def downgrade():
    pass
