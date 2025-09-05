from sqlalchemy import text

"""
Normalize VM Display Device Port(s)

Revision ID: d46d345ef8a8
Revises: 696b3d876084
Create Date: 2022-03-28 20:20:11.823446+00:00

"""
import json

from alembic import op


revision = 'd46d345ef8a8'
down_revision = '696b3d876084'
branch_labels = None
depends_on = None


def get_web_port(port):
    split_port = int(str(port)[:2]) - 1
    return int(str(split_port) + str(port)[2:])


def upgrade():
    conn = op.get_bind()
    # ensure vnc port

    display_devices = {
        row['id']: json.loads(row['attributes'])
        for row in map(dict, conn.execute(text("SELECT * FROM vm_device WHERE dtype = 'DISPLAY'")).fetchall())
    }
    reserved_ports = [d['port'] for d in display_devices.values()] + [6000]

    for display_id, display_device in display_devices.items():
        web_port = get_web_port(display_device['port'])
        while web_port in reserved_ports:
            web_port += 1
        display_device['web_port'] = web_port
        reserved_ports.append(web_port)
        conn.execute("UPDATE vm_device SET attributes = ? WHERE id = ?", (
            json.dumps(display_device), display_id
        ))


def downgrade():
    pass
