"""Add exporting table for reporting

Revision ID: 3e16b0a74d78
Revises: e915a3b8fff6
Create Date: 2023-09-07 19:50:42.678757+00:00

"""
import json
import sqlalchemy as sa

from alembic import op
from sqlalchemy.sql import text


revision = '3e16b0a74d78'
down_revision = 'e915a3b8fff6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'reporting_exporters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('attributes', sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reporting_exports'))
    )

    conn = op.get_bind()

    for graphite_ip in filter(lambda ip: bool(ip[0]), conn.execute('SELECT graphite FROM system_reporting').fetchall()):
        attributes = {
            'destination_ip': graphite_ip[0],
            'destination_port': 2003,
            'prefix': 'dragonfish',
            'hostname': 'truenas',
            'update_every': 1,
            'buffer_on_failures': 10,
            'send_names_instead_of_ids': True,
            'matching_charts': '*'
        }
        query = text(
            'INSERT INTO reporting_exporters (enabled, type, name, attributes) VALUES '
            '(:enabled, :type, :name, :attributes)'
        )
        conn.execute(
            query,
            enabled=True,
            type='GRAPHITE',
            name='netdata',
            attributes=json.dumps(attributes)
        )

    op.drop_table('system_reporting')


def downgrade():
    pass
