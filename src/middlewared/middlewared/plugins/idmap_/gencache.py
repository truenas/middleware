import enum
import wbclient

from middlewared.service import Service
from middlewared.service_exception import MatchNotFound
from middlewared.utils import filter_list
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBDataType,
    TDBError,
    TDBOptions,
    TDBPathType,
)

GENCACHE_FILE = '/var/run/samba-lock/gencache.tdb'
GENCACHE_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)


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


def flush_gencache_entries() -> None:
    """
    delete all keys in gencache

    This matches behavior of "net cache flush" which iterates and
    deletes entries. If we fail due to corrupt TDB file then it will
    be wiped.
    """
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        for entry in hdl.entries():
            hdl.delete(entry['key'])


def query_gencache_entries(filters: list, options: dict) -> list | dict:
    with get_tdb_handle(GENCACHE_FILE, GENCACHE_TDB_OPTIONS) as hdl:
        return filter_list(hdl.entries(), filters, options)


class Gencache(Service):

    class Config:
        namespace = 'idmap.gencache'
        cli_private = True
        private = True

    def __construct_gencache_key(self, data):
        cache_type = IDMAPCacheType[data['entry_type']]
        match cache_type:
            case IDMAPCacheType.UID2SID | IDMAPCacheType.GID2SID:
                parsed_entry = data['entry']
                if not isinstance(parsed_entry, int):
                    raise ValueError(f'{parsed_entry}: UID/GID must be integer')
            case IDMAPCacheType.SID2XID | IDMAPCacheType.SID2NAME:
                parsed_entry = data['entry'].upper()
                if not wbclient.sid_is_valid(parsed_entry):
                    raise ValueError(f'{parsed_entry}: not a valid SID')
            case IDMAPCacheType.NAME2SID:
                parsed_entry = data['entry'].upper()
            case _:
                raise NotImplementedError(data["entry_type"])

        return f'{cache_type.value}/{parsed_entry}'

    def get_idmap_cache_entry(self, data):
        key = self.__construct_gencache_key(data)
        return fetch_gencache_entry(key)

    def del_idmap_cache_entry(self, data):
        key = self.__construct_gencache_key(data)
        try:
            return remove_gencache_entry(key)
        except RuntimeError as e:
            if len(e.args) == 0:
                raise e from None

            match e.args[0]:
                case TDBError.CORRUPT:
                    wipe_gencache_entries()
                    raise e from None
                case TDBError.NOEXIST:
                    raise MatchNotFound(key) from None
                case _:
                    raise e from None

    def flush(self):
        """
        Perform equivalent of `net cache flush`.
        """
        try:
            flush_gencache_entries()
        except RuntimeError as e:
            if len(e.args) == 0 or e.args[0] != TDBError.CORRUPT:
                raise e from None

            wipe_gencache_entries()
