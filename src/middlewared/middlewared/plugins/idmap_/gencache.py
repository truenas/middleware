import enum
import wbclient

from middlewared.service import Service
from middlewared.service_exception import MatchNotFound
from middlewared.plugins.tdb.utils import TDBError

GENCACHE_FILE = '/var/run/samba-lock/gencache.tdb'


class IDMAPCacheType(enum.Enum):
    UID2SID = 'IDMAP/UID2SID'
    GID2SID = 'IDMAP/GID2SID'
    SID2XID = 'IDMAP/SID2XID'
    SID2NAME = 'SID2NAME'
    NAME2SID = 'NAME2SID'


class Gencache(Service):

    class Config:
        namespace = 'idmap.gencache'
        cli_private = True
        private = True

    tdb_options = {
        'backend': 'CUSTOM',
        'data_type': 'BYTES'
    }

    async def __fetch(self, key):
        return await self.middleware.call('tdb.fetch', {
            'name': GENCACHE_FILE,
            'key': key,
            'tdb-options': self.tdb_options
        })

    async def __remove(self, key):
        return await self.middleware.call('tdb.remove', {
            'name': GENCACHE_FILE,
            'key': key,
            'tdb-options': self.tdb_options
        })

    async def __wipe(self):
        return await self.middleware.call('tdb.wipe', {
            'name': GENCACHE_FILE,
            'tdb-options': self.tdb_options
        })

    async def __flush(self):
        return await self.middleware.call('tdb.flush', {
            'name': GENCACHE_FILE,
            'tdb-options': self.tdb_options
        })

    async def __construct_gencache_key(self, data):
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

    async def get_idmap_cache_entry(self, data):
        key = await self.__construct_gencache_key(data)
        return await self.__fetch(key)

    async def del_idmap_cache_entry(self, data):
        key = await self.__construct_gencache_key(data)
        try:
            return await self.__remove(key)
        except RuntimeError as e:
            if len(e.args) == 0:
                raise e from None

            match e.args[0]:
                case TDBError.CORRUPT:
                    await self.wipe()
                    raise e from None
                case TDBError.NOEXIST:
                    raise MatchNotFound(key) from None
                case _:
                    raise e from None

    async def flush(self):
        """
        Perform equivalent of `net cache flush`.
        """
        try:
            await self.__flush()
        except RuntimeError as e:
            if len(e.args) == 0 or e.args[0] != TDBError.CORRUPT:
                raise e from None

            await self.__wipe()
