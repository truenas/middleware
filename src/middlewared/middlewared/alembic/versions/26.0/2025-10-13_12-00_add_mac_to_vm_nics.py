"""Add MAC addresses to VM NIC devices that don't have them

Revision ID: c3f8d9e2a4b1
Revises: 809c51228665
Create Date: 2025-10-13 12:00:00.000000+00:00

"""
import json
import random

from alembic import op
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt, encrypt


# revision identifiers, used by Alembic.
revision = 'c3f8d9e2a4b1'
down_revision = '809c51228665'
branch_labels = None
depends_on = None


def random_mac() -> str:
    """Generate a random MAC address for VM NICs."""
    mac_address = [
        0x00, 0xa0, 0x98, random.randint(0x00, 0x7f), random.randint(0x00, 0xff), random.randint(0x00, 0xff)
    ]
    return ':'.join(['%02x' % x for x in mac_address])


def upgrade():
    conn = op.get_bind()

    for row in conn.execute(text("SELECT * FROM vm_device")).mappings().all():
        attributes = json.loads(decrypt(row['attributes']))

        if attributes.get('dtype') != 'NIC':
            continue

        if not attributes.get('mac'):
            attributes['mac'] = random_mac()
            conn.execute(
                text("UPDATE vm_device SET attributes = :attrs WHERE id = :id"),
                {"attrs": encrypt(json.dumps(attributes)), "id": row['id']}
            )


def downgrade():
    pass
