from sqlalchemy import text

"""update usb pass through params

Revision ID: d388b0e9a50d
Revises: 7a74a8933a30
Create Date: 2022-10-07 21:31:21.541782+00:00

"""
from alembic import op
import json

revision = 'd388b0e9a50d'
down_revision = '7a74a8933a30'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    devices = {
        row['id']: json.loads(row['attributes'])
        for row in map(dict, conn.execute(text("SELECT * FROM vm_device WHERE dtype = 'USB'")).fetchall())
    }

    for device_id, device_attrs in devices.items():
        device_attrs.update({
            'controller_type': 'nec-xhci',
            'usb': None,
        })
        conn.execute(text('UPDATE vm_device SET attributes = :attrs WHERE id = :id'), {
            'attrs': json.dumps(device_attrs), 'id': device_id
        })


def downgrade():
    pass
