from sqlalchemy import text

"""
Normalize Remote Display VM device

Revision ID: 382b7ca9bb51
Revises: d9e9d467fb39
Create Date: 2021-02-10 00:23:15.609666+00:00

"""
import json

from alembic import op

revision = '382b7ca9bb51'
down_revision = 'd9e9d467fb39'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    vnc_devices = list(map(dict, conn.execute(text("SELECT * FROM vm_device WHERE dtype = 'VNC'")).fetchall()))

    for device in vnc_devices:
        attrs = json.loads(device['attributes'])
        attrs.update({
            'port': attrs.pop('vnc_port'),
            'resolution': attrs.pop('vnc_resolution', '1024x768') or '1024x768',
            'bind': attrs.pop('vnc_bind'),
            'password': attrs.pop('vnc_password', None),
            'web': attrs.pop('vnc_web', True),
            'type': 'VNC',
        })
        conn.execute(text("UPDATE vm_device SET attributes = :attrs, dtype = 'DISPLAY' WHERE id = :id"), {
            "attrs": json.dumps(attrs), "id": device['id']
        })


def downgrade():
    pass
