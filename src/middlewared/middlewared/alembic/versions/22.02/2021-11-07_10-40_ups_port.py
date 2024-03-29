"""
Normalize UPS Port choice

Revision ID: 91b71800c7fe
Revises: 5e4a6dbd7bd2
Create Date: 2021-11-07 10:40:05.030458+00:00

"""
import os

from alembic import op


revision = '91b71800c7fe'
down_revision = '5e4a6dbd7bd2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    sys_config = [dict(row) for row in conn.execute("SELECT * FROM system_advanced").fetchall()]
    ups_config = [dict(row) for row in conn.execute("SELECT * FROM services_ups").fetchall()]
    if not sys_config or not ups_config:
        return

    serial_port = os.path.join('/dev', sys_config[0]['adv_serialport'] or '')
    ups_port = ups_config[0]['ups_port']

    if serial_port == ups_port:
        conn.execute("UPDATE services_ups SET ups_port = ? WHERE id = ?", ('', ups_config[0]['id']))


def downgrade():
    pass
