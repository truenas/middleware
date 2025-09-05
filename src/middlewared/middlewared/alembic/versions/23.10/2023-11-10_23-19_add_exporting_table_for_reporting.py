"""Add exporting table for reporting

Revision ID: 8f8942557260
Revises: 304e43883592
Create Date: 2023-11-10 23:19:42.678757+00:00

"""
import json
import sqlalchemy as sa

from alembic import op
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql import text


revision = '8f8942557260'
down_revision = '304e43883592'
branch_labels = None
depends_on = None


def get_hostname(conn):
    try:
        return dict(conn.execute(text('SELECT * FROM network_globalconfiguration')).fetchone())['gc_hostname']
    except Exception:
        return 'truenas'


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    if 'reporting_exporters' in inspector.get_table_names():
        return  # Skip if already migrated

    op.create_table(
        'reporting_exporters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('attributes', sa.TEXT(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reporting_exports'))
    )

    hostname = get_hostname(conn)
    for graphite_ip in filter(lambda ip: bool(ip[0]), conn.execute(text('SELECT graphite FROM system_reporting')).fetchall()):
        attributes = {
            'destination_ip': graphite_ip[0],
            'destination_port': 2003,
            'prefix': 'scale',
            'hostname': hostname,
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
