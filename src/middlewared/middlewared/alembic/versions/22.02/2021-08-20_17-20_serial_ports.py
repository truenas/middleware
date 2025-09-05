"""
User serial port(s) name instead of I/O address

Revision ID: 725b7264abe6
Revises: 29abd3dce632
Create Date: 2021-20-08 17:20:42.818433+00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from middlewared.utils.serial import serial_port_choices


revision = '725b7264abe6'
down_revision = '29abd3dce632'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    io_choices = {e['start']: e['name'] for e in serial_port_choices()}
    sys_config = [dict(row) for row in conn.execute(text("SELECT * FROM system_advanced")).fetchall()]
    if not sys_config:
        return

    sys_config = sys_config[0]
    if sys_config['adv_serialport'] not in io_choices:
        new_val = 'ttyS0'
    else:
        new_val = io_choices[sys_config['adv_serialport']]

    conn.execute("UPDATE system_advanced SET adv_serialport = ? WHERE id = ?", (new_val, sys_config['id']))


def downgrade():
    pass
