"""
Allow users to configure NDP for vms

Revision ID: 75d84034adcb
Revises: 3ac384af617f
Create Date: 2022-07-26 17:20:58.755371+00:00

"""
import json

from alembic import op
from sqlalchemy import text


revision = '75d84034adcb'
down_revision = '3ac384af617f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    for row in conn.execute(text("SELECT * FROM vm_device WHERE dtype = 'NIC'")).mappings().all():
        config = json.loads(row['attributes'])
        config['trust_guest_rx_filters'] = False
        conn.execute(
            text("UPDATE vm_device SET attributes = :attrs WHERE id = :id"),
            {"attrs": json.dumps(config), "id": row['id']}
        )


def downgrade():
    pass
