"""
Remove novnc support from display devices

Revision ID: 9a94fb8c0206
Revises: a1917e15f409
Create Date: 2023-07-15 03:07:14.561629+00:00

"""
import json

from alembic import op
from collections import defaultdict


revision = '9a94fb8c0206'
down_revision = 'a1917e15f409'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    to_remove_ids = []
    vms_mapping = defaultdict(list)
    for row in map(dict, conn.execute("SELECT * FROM vm_device WHERE dtype = 'DISPLAY'").fetchall()):
        vms_mapping[row['vm_id']].append(row)

    for devices in vms_mapping.values():
        if len(devices) == 1:
            device = devices[0]
            device['attributes'] = json.loads(device['attributes'])
            if device['attributes']['type'] == 'VNC':
                device['attributes']['type'] = 'SPICE'
                conn.execute('UPDATE vm_device SET attributes = ? WHERE id = ?', (
                    json.dumps(device['attributes']), device['id']
                ))
        else:
            for device in devices:
                device['attributes'] = json.loads(device['attributes'])
                if device['attributes']['type'] == 'VNC':
                    to_remove_ids.append(device['id'])

    for remove_id in to_remove_ids:
        conn.execute('DELETE FROM vm_device WHERE id = ?', (remove_id,))


def downgrade():
    pass
