"""Identify USB passthrough devices by sysfs port path

The `device` attribute held a libvirt nodedev name, which the underlying
library has since redefined, so the stored value no longer means what it used
to. It is replaced by `port`, holding the sysfs port path the old names encoded
anyway. Devices whose stored identity cannot be turned into something the API
is able to read back lose their row.

Revision ID: a7e91c4d0b52
Revises: 1dc145b1f6fa
Create Date: 2026-08-04 10:00:00.000000+00:00

"""
import json
import logging

from alembic import op
from sqlalchemy import text

from middlewared.utils.pwenc import decrypt, encrypt
from middlewared.utils.usb import migrate_usb_device_attributes


# revision identifiers, used by Alembic.
revision = 'a7e91c4d0b52'
down_revision = '1dc145b1f6fa'
branch_labels = None
depends_on = None

logger = logging.getLogger('alembic.runtime.migration')

# Whether a `device` value stored in each table can be read as a physical port at all.
#
# Up to and including 25.10, a `vm_device` `device` held a libvirt nodedev name, and those names
# were built out of the sysfs port path, so they can be reinterpreted as one.
#
# `container_device` is a different story. The table was created in 26.0 and has never existed in
# any earlier release, so every USB row in it was written by 26.0 code, and 26.0 code stored
# `usb_<bus>_<devnum>`. A device number is an enumeration counter the kernel reissues on every
# replug, and nothing short of the live hardware can map one back to a port. A migration cannot go
# looking for it either, since it also replays against databases uploaded from other machines. So
# those rows are dropped rather than aimed at whichever port the digits happen to spell.
DEVICE_IS_PORT_PATH = {
    'vm_device': True,
    'container_device': False,
}


def upgrade():
    conn = op.get_bind()

    for table, device_is_port_path in DEVICE_IS_PORT_PATH.items():
        for row in conn.execute(text(f"SELECT * FROM {table}")).mappings().all():
            if not (decrypted := decrypt(row['attributes'])):
                continue

            attributes = json.loads(decrypted)

            if attributes.get('dtype') != 'USB':
                continue

            updated, drop_reason = migrate_usb_device_attributes(
                attributes, device_is_port_path=device_is_port_path
            )

            if updated is None:
                identity = {key: attributes[key] for key in ('device', 'port', 'usb') if key in attributes}
                logger.warning(
                    'Removing %s row %r with USB identity %r: %s. The device has to be added again.',
                    table, row['id'], identity, drop_reason,
                )
                conn.execute(
                    text(f"DELETE FROM {table} WHERE id = :id"),
                    {'id': row['id']},
                )
            elif updated != attributes:
                conn.execute(
                    text(f"UPDATE {table} SET attributes = :attrs WHERE id = :id"),
                    {'attrs': encrypt(json.dumps(updated)), 'id': row['id']},
                )


def downgrade():
    pass
