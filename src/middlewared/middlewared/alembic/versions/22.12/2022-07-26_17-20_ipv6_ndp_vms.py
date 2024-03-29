"""
Allow users to configure NDP for vms

Revision ID: 75d84034adcb
Revises: 3ac384af617f
Create Date: 2022-07-26 17:20:58.755371+00:00

"""
import json

from alembic import op



revision = '75d84034adcb'
down_revision = '3ac384af617f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    for row in map(dict, conn.execute("SELECT * FROM vm_device WHERE dtype = 'NIC'").fetchall()):
        config = json.loads(row['attributes'])
        config['trust_guest_rx_filters'] = False
        conn.execute("UPDATE vm_device SET attributes = ? WHERE id = ?", (json.dumps(config), row['id']))


def downgrade():
    pass
