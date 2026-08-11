"""Normalize NIC MAC addresses to libvirt's colon-separated form

Revision ID: 9c31be47d5a2
Revises: 1dc145b1f6fa
Create Date: 2026-08-06 12:00:00.000000+00:00

"""

import json
import random
import re

from alembic import op
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt, encrypt


# revision identifiers, used by Alembic.
revision = "9c31be47d5a2"
down_revision = "1dc145b1f6fa"
branch_labels = None
depends_on = None


def random_mac() -> str:
    mac_address = [0x00, 0xA0, 0x98, random.randint(0x00, 0x7F), random.randint(0x00, 0xFF), random.randint(0x00, 0xFF)]
    return ":".join(["%02x" % x for x in mac_address])


def normalize_mac(mac) -> str:
    if not isinstance(mac, str):
        return random_mac()

    # libvirt's defineXML only parses colon-separated MACs. Older releases stored dash, no-separator,
    # mixed and uppercase forms; collapse anything that carries a valid 48-bit address to the canonical
    # lowercase colon form, and regenerate the rare value that isn't a MAC at all.
    hexed = re.sub(r"[:-]", "", mac).lower()
    if re.fullmatch(r"[0-9a-f]{12}", hexed):
        return ":".join(hexed[i : i + 2] for i in range(0, 12, 2))
    return random_mac()


def upgrade():
    conn = op.get_bind()

    for table in ("vm_device", "container_device"):
        for row in conn.execute(text(f"SELECT * FROM {table}")).mappings().all():
            if not (decrypted := decrypt(row["attributes"])):
                continue

            attributes = json.loads(decrypted)

            if attributes.get("dtype") != "NIC" or not attributes.get("mac"):
                continue

            normalized = normalize_mac(attributes["mac"])
            if normalized != attributes["mac"]:
                attributes["mac"] = normalized
                conn.execute(
                    text(f"UPDATE {table} SET attributes = :attrs WHERE id = :id"),
                    {"attrs": encrypt(json.dumps(attributes)), "id": row["id"]},
                )


def downgrade():
    pass
