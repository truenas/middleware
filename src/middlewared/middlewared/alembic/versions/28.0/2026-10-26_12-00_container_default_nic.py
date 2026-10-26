"""Give containers without a NIC device one on the configured bridge

Revision ID: c9ebd3e3cfbc
Revises: 2f08b4c7a1d9
Create Date: 2026-10-26 12:00:00.000000+00:00

"""

import json
import random

from alembic import op
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt, encrypt


# revision identifiers, used by Alembic.
revision = "c9ebd3e3cfbc"
down_revision = "2f08b4c7a1d9"
branch_labels = None
depends_on = None


def random_mac() -> str:
    mac_address = [0x00, 0xA0, 0x98, random.randint(0x00, 0x7F), random.randint(0x00, 0xFF), random.randint(0x00, 0xFF)]
    return ":".join(["%02x" % x for x in mac_address])


def upgrade():
    conn = op.get_bind()

    bridge = conn.execute(text("SELECT bridge FROM container_config LIMIT 1")).scalar() or "truenasbr0"

    skip = set()
    for row in conn.execute(text("SELECT container_id, attributes FROM container_device")).mappings().all():
        decrypted = decrypt(row["attributes"])
        if not decrypted or json.loads(decrypted).get("dtype") == "NIC":
            skip.add(row["container_id"])

    for container_id in conn.execute(text("SELECT id FROM container_container")).scalars().all():
        if container_id in skip:
            continue

        attributes = {
            "dtype": "NIC",
            "nic_attach": bridge,
            "type": "VIRTIO",
            "trust_guest_rx_filters": False,
            "mac": random_mac(),
        }
        conn.execute(
            text("INSERT INTO container_device (attributes, container_id) VALUES (:attrs, :container_id)"),
            {"attrs": encrypt(json.dumps(attributes)), "container_id": container_id},
        )


def downgrade():
    pass
