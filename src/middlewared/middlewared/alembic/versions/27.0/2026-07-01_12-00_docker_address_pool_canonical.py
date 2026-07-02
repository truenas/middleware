"""Normalize Docker address pool base networks to their canonical form

Revision ID: 28e5285cfb2d
Revises: c1d2e3f4a5b6
Create Date: 2026-07-01 12:00:00.000000+00:00

"""

import ipaddress
import json
import logging

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "28e5285cfb2d"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade():
    conn = op.get_bind()

    row = conn.execute(text("SELECT id, address_pools FROM services_docker")).fetchone()
    if not row:
        return

    try:
        address_pools = json.loads(row[1])
    except (TypeError, ValueError):
        return

    # Docker ignores host bits in an address pool base, e.g. a base of 172.17.0.0/12 is treated as
    # 172.16.0.0/12 and networks are allocated from 172.16.0.0 upwards. Historically the default and
    # user input were stored verbatim, so the value shown in the UI / written to daemon.json did not
    # match the network Docker actually used. Normalize any stored base to its canonical network
    # address so the configured pool matches the effective pool. This is a no-op for Docker.
    changed = False
    for pool in address_pools:
        base = pool.get("base")
        if not isinstance(base, str):
            continue
        try:
            canonical = str(ipaddress.ip_network(base, strict=False))
        except ValueError:
            continue
        if canonical != base:
            logger.info("Normalizing Docker address pool base %r to %r", base, canonical)
            pool["base"] = canonical
            changed = True

    if changed:
        conn.execute(
            text("UPDATE services_docker SET address_pools = :address_pools WHERE id = :id"),
            {"address_pools": json.dumps(address_pools), "id": row[0]},
        )


def downgrade():
    pass
