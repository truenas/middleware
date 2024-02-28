import time
import uuid

from .utils import AUDIT_CACHE_FILE
from middlewared.service import Service
from middlewared.service_exception import MatchNotFound

CACHE_DATA_SUFFIX = '_data'
CACHE_TIMESTAMP_SUFFIX = '_ts'


class AuditCacheService(Service):
    class Config:
        private = True
        namespace = 'audit.cache'

    tdb_options = {
        'backend': 'CUSTOM',
        'data_type': 'JSON'
    }

    async def store(self, app, data, ttl=360):
        """
        Write timestamp and data entries for UUID under a transaction
        lock in the cache file in /audit directory. Since cache is persistent
        the timeout is based on realtime clock.

        audit.query should be only consumer of this endpoint.
        """
        entry_uuid = str(uuid.uuid4())
        timeout = time.time() + ttl
        await self.middleware.call('tdb.batch_ops', {
            'name': AUDIT_CACHE_FILE,
            'ops': [
                {
                    'action': 'SET',
                    'key': f'{entry_uuid}{CACHE_DATA_SUFFIX}',
                    'val': data
                },
                {
                    'action': 'SET',
                    'key': f'{entry_uuid}{CACHE_TIMESTAMP_SUFFIX}',
                    'val': {'timeout': timeout, 'credential': app.authenticated_credentials.dump()}
                },
            ],
            'tdb-options': self.tdb_options
        })
        return entry_uuid

    async def fetch(self, app, entry_uuid):
        """
        Fetch audit result cache by uuid. This should only be consumed by audit.query.
        """
        ts = await self.middleware.call('tdb.fetch', {
            'name': AUDIT_CACHE_FILE,
            'key': f'{entry_uuid}{CACHE_TIMESTAMP_SUFFIX}',
            'tdb-options': self.tdb_options
        })

        now = time.time()
        if now > ts['timeout']:
            try:
                await self.__remove(entry_uuid)
            except Exception:
                self.logger.error('%s: failed to remove expired entry', uuid, exc_info=True)

            raise MatchNotFound

        return await self.middleware.call('tdb.fetch', {
            'name': AUDIT_CACHE_FILE,
            'key': f'{entry_uuid}{CACHE_DATA_SUFFIX}',
            'tdb-options': self.tdb_options
        })

    async def __remove(self, entry_uuid):
        """
        Remove entries for UUID under a transaction lock
        """
        await self.middleware.call('tdb.batch_ops', {
            'name': AUDIT_CACHE_FILE,
            'ops': [
                {'action': 'DEL', 'key': f'{entry_uuid}{CACHE_DATA_SUFFIX}'},
                {'action': 'DEL', 'key': f'{entry_uuid}{CACHE_TIMESTAMP_SUFFIX}'},
            ],
            'tdb-options': self.tdb_options
        })

    async def cleanup(self):
        try:
            entries = await self.middleware.call('tdb.entries', {
                'name': AUDIT_CACHE_FILE,
                'query-filters': [['key', '$', CACHE_TIMESTAMP_SUFFIX]],
                'tdb-options': self.tdb_options
            })
        except FileNotFoundError:
            entries = []

        now = time.time()

        for entry in entries:
            if now > entry['val']['timeout']:
                await self.__remove(entry['key'].strip(CACHE_TIMESTAMP_SUFFIX))
