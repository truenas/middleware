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

    session_ids_with_reports = []

    async def store(self, app, query, data, ttl=300):
        """
        Write timestamp and data entries for specified session_id under a
        transaction lock in the cache file in /audit directory. Since cache is
        persistent the timeout is based on realtime clock.

        audit.query should be only consumer of this endpoint.
        """
        session_id = app.session_id

        if session_id not in self.session_ids_with_reports:
            self.session_ids_with_reports.append(session_id)

        timeout = time.time() + ttl
        await self.middleware.call('tdb.batch_ops', {
            'name': AUDIT_CACHE_FILE,
            'ops': [
                {
                    'action': 'SET',
                    'key': f'{session_id}{CACHE_DATA_SUFFIX}',
                    'val': data
                },
                {
                    'action': 'SET',
                    'key': f'{session_id}{CACHE_TIMESTAMP_SUFFIX}',
                    'val': {
                        'timeout': timeout,
                        'credential': app.authenticated_credentials.dump(),
                        'query': query
                    }
                },
            ],
            'tdb-options': self.tdb_options
        })

    async def fetch(self, session_id, query):
        """
        Fetch audit result cache by session_id. This should only be consumed by audit.query.

        Cached result only returned if:
        1. TTL hasn't expired
        2. query-filters matches exactly
        3. query-options does not match (pagination shift)
        4. services queried matches exactly

        If cached result is stale, we remove proactively from tdb
        """
        def must_invalidate_cache():
            if ts['query']['services'] != query['services']:
                return True

            if ts['query']['query-filters'] != query['query-filters']:
                return True

            if ts['query']['query-options'] == query['query-options']:
                return True

            return False

        ts = await self.middleware.call('tdb.fetch', {
            'name': AUDIT_CACHE_FILE,
            'key': f'{session_id}{CACHE_TIMESTAMP_SUFFIX}',
            'tdb-options': self.tdb_options
        })

        now = time.time()
        if now > ts['timeout']:
            try:
                await self.remove(session_id)
            except Exception:
                self.logger.error('%s: failed to remove expired entry', session_id, exc_info=True)

            raise MatchNotFound

        if must_invalidate_cache():
            try:
                await self.remove(session_id)
            except Exception:
                self.logger.error('%s: failed to remove invalidated entry', session_id, exc_info=True)

            raise MatchNotFound

        return await self.middleware.call('tdb.fetch', {
            'name': AUDIT_CACHE_FILE,
            'key': f'{session_id}{CACHE_DATA_SUFFIX}',
            'tdb-options': self.tdb_options
        })

    async def remove(self, session_id, strict=True):
        """
        Remove entries for UUID under a transaction lock
        """
        if not strict and session_id not in self.session_ids_with_reports:
            return

        await self.middleware.call('tdb.batch_ops', {
            'name': AUDIT_CACHE_FILE,
            'ops': [
                {'action': 'DEL', 'key': f'{session_id}{CACHE_DATA_SUFFIX}'},
                {'action': 'DEL', 'key': f'{session_id}{CACHE_TIMESTAMP_SUFFIX}'},
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
                await self.remove(entry['key'].strip(CACHE_TIMESTAMP_SUFFIX))


async def handle_session_event(middleware, event_type, args):
    if event_type != 'REMOVED':
        return

    await middleware.call('audit.cache.remove', args['fields']['id'], False)


async def setup(middleware):
    middleware.event_subscribe('auth.sessions', handle_session_event)
