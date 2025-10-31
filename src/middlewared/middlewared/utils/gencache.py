import enum

from middlewared.utils.filter_list import filter_list
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBDataType,
    TDBOptions,
    TDBPathType,
)

GENCACHE_FILE = '/var/run/samba-lock/gencache.tdb'
GENCACHE_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)
SAFKEY_PREFIX = 'SAF/DOMAIN'
SAFJOIN_PREFIX = 'SAFJOIN/DOMAIN'


class IDMAPCacheType(enum.Enum):
    UID2SID = 'IDMAP/UID2SID'
    GID2SID = 'IDMAP/GID2SID'
    SID2XID = 'IDMAP/SID2XID'
    SID2NAME = 'SID2NAME'
    NAME2SID = 'NAME2SID'


def fetch_gencache_entry(key: str) -> str:
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        return hdl.get(key)


def store_gencache_entry(key: str, val: str) -> None:
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        return hdl.store(key, val)


def remove_gencache_entry(key: str) -> None:
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        return hdl.delete(key)


def wipe_gencache_entries() -> None:
    """ wrapper around tdb_wipe_all for file """
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        return hdl.clear()


def flush_gencache_entries(keep_saf=False) -> None:
    """
    delete all keys in gencache

    This matches behavior of "net cache flush" which iterates and
    deletes entries. If we fail due to corrupt TDB file then it will
    be wiped.

    keep_saf: the winbindd connection manager uses gencache keys to
    keep track of the last DC it successfully talked to. Keeping the
    winbindd saf cache across flushing other entries will help to
    avoid service disruptions if we need to only wipe user / group
    entries.
    """
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        for entry in hdl.entries():
            if keep_saf and entry['key'].startswith((SAFKEY_PREFIX, SAFJOIN_PREFIX)):
                continue

            hdl.delete(entry['key'])


def query_gencache_entries(filters: list, options: dict) -> list | dict:
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        return filter_list(hdl.entries(), filters, options)
