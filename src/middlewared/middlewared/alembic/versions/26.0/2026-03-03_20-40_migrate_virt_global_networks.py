"""Migrate virt_global network settings to container_config (lxc.config)

Revision ID: f3b4b0f4b0cf
Revises: a4b1e7f9c2d5
Create Date: 2026-03-03 20:40:00.000000+00:00

"""
import ipaddress

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'f3b4b0f4b0cf'
down_revision = 'a4b1e7f9c2d5'
branch_labels = None
depends_on = None

# Network defaults for the auto-managed container bridge (truenasbr0).
# Chosen to avoid overlap with:
#   - Docker address pools: 172.17.0.0/12 (v4), fdd0::/48 (v6)
#   - Incus auto-generated ranges: 10.x.x.0/24 (v4), fd42:random::/64 (v6)
# Must stay in sync with defaults in container/config.py ContainerConfigModel.
DEFAULT_V4_NETWORK = '172.200.0.0/24'
DEFAULT_V6_NETWORK = 'fd42:4c58:43ae::/64'


def _normalize_network(value):
    """Strip host bits: '10.254.203.1/24' -> '10.254.203.0/24'"""
    try:
        return str(ipaddress.ip_network(value, strict=False))
    except (ValueError, TypeError):
        return None


def upgrade():
    conn = op.get_bind()

    row = conn.execute(text("SELECT * FROM container_config LIMIT 1")).mappings().first()

    # Migrate data only when there is a row with NULL network columns.
    if row is not None:
        container = dict(row)

        if any(container[k] is None for k in ('v4_network', 'v6_network', 'bridge')):
            # Try migrating NULL columns from the legacy virt_global table (pre-26.0 Incus setup).
            # virt_global stored host addresses like '10.254.203.1/24'; we normalize
            # them to network addresses like '10.254.203.0/24'.
            virt_row = conn.execute(text("SELECT * FROM virt_global LIMIT 1")).mappings().first()
            if virt_row is not None:
                virt = dict(virt_row)

                updates = {}
                for col in ('bridge', 'v4_network', 'v6_network'):
                    if container[col] is not None or not virt.get(col):
                        continue

                    value = virt[col]
                    if col in ('v4_network', 'v6_network'):
                        value = _normalize_network(value)
                        if value is None:
                            continue

                    updates[col] = value

                if updates:
                    set_clause = ', '.join(f'{col} = :{col}' for col in updates)
                    conn.execute(
                        text(f"UPDATE container_config SET {set_clause} WHERE id = :id"),
                        {**updates, 'id': container['id']},
                    )

            # Apply defaults for any network columns still NULL after virt_global migration.
            conn.execute(text(
                "UPDATE container_config"
                f" SET v4_network = COALESCE(v4_network, '{DEFAULT_V4_NETWORK}'),"
                f"     v6_network = COALESCE(v6_network, '{DEFAULT_V6_NETWORK}')"
                " WHERE v4_network IS NULL OR v6_network IS NULL"
            ))

    # Always enforce NOT NULL
    with op.batch_alter_table('container_config') as batch_op:
        batch_op.alter_column('v4_network', existing_type=sa.String(), nullable=False,
                              server_default=DEFAULT_V4_NETWORK)
        batch_op.alter_column('v6_network', existing_type=sa.String(), nullable=False,
                              server_default=DEFAULT_V6_NETWORK)


def downgrade():
    pass
