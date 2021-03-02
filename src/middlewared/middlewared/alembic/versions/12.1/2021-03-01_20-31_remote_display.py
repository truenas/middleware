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

    vnc_devices = [dict(row) for row in conn.execute("SELECT * FROM vm_device WHERE dtype = 'VNC'").fetchall()]

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
        conn.execute("UPDATE vm_device SET attributes = ?, dtype = 'DISPLAY' WHERE id = ?", (
            json.dumps(attrs), device['id']
        ))


def downgrade():
    pass
