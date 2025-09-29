from sqlalchemy import text

"""Ensure iSCSI extents have a non-empty serial number.

Revision ID: fa33f4ae6427
Revises: b06ea181e7dd
Create Date: 2023-10-02 21:57:49.452962+00:00

"""
from alembic import op
import secrets


# revision identifiers, used by Alembic.
revision = 'fa33f4ae6427'
down_revision = 'b06ea181e7dd'
branch_labels = None
depends_on = None


def generate_serial(used_serials, tries=10):
    for i in range(tries):
        serial = secrets.token_hex()[:15]
        if serial not in used_serials:
            return serial


def upgrade():
    # We wish to ensure that every iSCSI extent has a (unique) serial number
    # assigned (but that said we will only change the serial number if
    # previously empty)
    conn = op.get_bind()
    tofix = []
    for (ident,) in conn.execute(text("SELECT id FROM services_iscsitargetextent WHERE iscsi_target_extent_serial == null or iscsi_target_extent_serial == ''")):
        tofix.append(ident)
    if tofix:
        serials = []
        for (serial,) in conn.execute(text("SELECT iscsi_target_extent_serial FROM services_iscsitargetextent")):
            if serial not in [None, '']:
                serials.append(serial)
        for ident in tofix:
            serial = generate_serial(serials)
            if serial:
                conn.execute(
                    text(
                        "UPDATE services_iscsitargetextent SET iscsi_target_extent_serial = :serial WHERE id = :ident"
                    ),
                    {
                        "serial": serial, "ident": ident
                    }
                )
                serials.append(serial)


def downgrade():
    pass
