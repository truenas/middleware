"""Get rid of autorid

Revision ID: 3d738dbd75ef
Revises: 4465da1dbb37
Create Date: 2025-07-14 12:22:17.431832+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from json import loads, dumps
from middlewared.utils.pwenc import encrypt, decrypt


# revision identifiers, used by Alembic.
revision = '3d738dbd75ef'
down_revision = '4465da1dbb37'
branch_labels = None
depends_on = None


def migrate_autorid_to_rid(conn, config: dict) -> None:
    """ This function converts an idmap_autorid configuration into a roughly equivalent idmap_rid configuration.
    Trusted domains are also disabled (if enabled) to allow admin to set up any relevant configuration before
    re-enabling. """
    idmap = loads(decrypt(config['ad_idmap']))
    if idmap['idmap_domain']['idmap_backend'] != 'AUTORID':
        return

    rangesize = idmap['idmap_domain']['rangesize']
    # Autorid sets offset for currently-joined domain at second rangesize increment
    range_low = idmap['idmap_domain']['range_low'] + rangesize
    range_high = idmap['idmap_domain']['range_high']

    new_domain = {
        'idmap_backend': 'RID',
        'sssd_compat': False,
        'range_low': range_low,
        'range_high': range_high
    }

    builtin = {
        'name': None,
        'range_low': idmap['idmap_domain']['range_low'],
        'range_high': idmap['idmap_domain']['range_low'] + 10000
    }

    new_idmap = encrypt(dumps({'builtin': builtin, 'idmap_domain': new_domain}))

    stmt = (
        'UPDATE directoryservices SET '
        'ad_idmap = :idmap, '
        'ad_enable_trusted_domains = 0'
    )
    conn.execute(text(stmt), {'idmap': new_idmap})


def upgrade():
    conn = op.get_bind()
    row = conn.execute(text('SELECT * FROM directoryservices')).mappings().first()
    if not row:
        return

    ds = dict(row)

    if ds['service_type'] != 'ACTIVEDIRECTORY':
        return

    migrate_autorid_to_rid(conn, ds)
