from middlewared.client import ejson as json
from middlewared.plugins.sysdataset import SYSDATASET_PATH
from middlewared.service import Service, private
from middlewared.schema import accepts, Bool, Dict, Ref, List, Str, Int
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils import filter_list
from .connection import TDBMixin
from .wrapper import TDBPath

import ctdb
import errno
import os
import threading

from base64 import b64encode, b64decode
from contextlib import contextmanager


class TDBService(Service, TDBMixin):

    handles = {}

    class Config:
        private = True

    @private
    def validate_tdb_options(self, name, options, skip_health_check):
        if not options['cluster'] or skip_health_check:
            return

        healthy = self.middleware.call_sync('ctdb.general.healthy')
        if healthy:
            return

        raise CallError(f"{name}: ctdb must be enabled and healthy.", errno.ENXIO)

    @private
    def _ctdb_get_dbid(self, name, options):
        db = ctdb.Ctdb(ctdb.Client(), f'{name}.tdb', os.O_CREAT)
        db.attach(ctdb.DB_PERSISTENT)
        return db.db_id

    @private
    @contextmanager
    def get_connection(self, name, options, skip_health_check=False):
        self.validate_tdb_options(name, options, skip_health_check)

        entry = self.handles.setdefault(name, {
            'name': name,
            'lock': threading.RLock(),
            'handle_internal': None,
            'options': options.copy()
        })

        if options != entry['options']:
            raise CallError(f'{name}: Internal Error - tdb options mismatch', errno.EINVAL)

        with entry['lock']:
            dbid = None
            if entry['handle_internal'] is None:
                if options['cluster']:
                    dbid = self._ctdb_get_dbid(name, options)

                entry['handle_internal'] = self._get_handle(name, dbid, options, self.logger)

            elif not entry['handle_internal'].validate_handle():
                entry['handle_internal'].close()
                if options['cluster']:
                    dbid = self._ctdb_get_dbid(name, options)

                entry['handle_internal'] = self._get_handle(name, dbid, options, self.logger)

            yield entry['handle_internal']

    @accepts(Dict(
        'tdb-store',
        Str('name', required=True),
        Str('key', required=True),
        Dict('value', required=True, additional_attrs=True),
        Dict(
            'tdb-options',
            Str('backend', enum=['PERSISTENT', 'VOLATILE', 'CUSTOM'], default='PERSISTENT'),
            Str('data_type', enum=['JSON', 'STRING', 'BYTES'], default='JSON'),
            Bool('cluster', default=False),
            Int('read_backoff', default=0),
            register=True
        )
    ))
    def store(self, data):
        """
        Store the `value` as `key`.
        """
        if data['tdb-options']['data_type'] == 'JSON':
            tdb_val = json.dumps(data['value'])
        elif data['tdb-options']['data_type'] == 'STRING':
            tdb_val = data['value']['payload']
        elif data['tdb-options']['data_type'] == 'BYTES':
            tdb_val = b64decode(data['value']['payload'])

        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._set(tdb_handle, data['key'], tdb_val)

    @accepts(Dict(
        'tdb-fetch',
        Str('name', required=True),
        Str('key', required=True),
        Ref('tdb-options'),
    ))
    def fetch(self, data):
        """
        Fetch the entry specified by `key`.
        """
        with self.get_connection(data['name'], data['tdb-options'], True) as tdb_handle:
            tdb_val = self._get(tdb_handle, data['key'])

        if tdb_val is None:
            raise MatchNotFound(data['key'])

        if data['tdb-options']['data_type'] == 'JSON':
            data = json.loads(tdb_val)
        elif data['tdb-options']['data_type'] == 'STRING':
            data = tdb_val
        elif data['tdb-options']['data_type'] == 'BYTES':
            data = b64encode(tdb_val).decode()

        return data

    @accepts(Dict(
        'tdb-remove',
        Str('name', required=True),
        Str('key', required=True),
        Ref('tdb-options'),
    ))
    def remove(self, data):
        """
        Remove the entry specified by `key`.
        """
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._rem(tdb_handle, data['key'])

    @accepts(Dict(
        Str('name', required=True),
        Ref('query-filters'),
        Ref('query-options'),
        Ref('tdb-options'),
    ))
    def entries(self, data):
        """
        query all entries in tdb file based on specified query-filters and query-options
        """
        def append_entries(tdb_key, tdb_data, state):
            if tdb_data is None:
                return True

            if state['key_filter'] and not filter_list([{'key': tdb_key}], state['key_filter'], {}):
                return True

            if state['data_type'] == 'JSON':
                entry = json.loads(tdb_data)
            elif state['data_type'] == 'STRING':
                entry = tdb_data
            elif state['data_type'] == 'BYTES':
                entry = b64encode(tdb_data).decode()

            state['output'].append({"key": tdb_key, "val": entry})
            return True

        state = {
            'output': [],
            'data_type': data['tdb-options']['data_type'],
            'key_filter': None
        }

        if len(data['query-filters']) == 1 and len(data['query-filters'][0]) == 3:
            if data['query-filters'][0][0] == 'key':
                state['key_filter'] = data['query-filters']

        with self.get_connection(data['name'], data['tdb-options'], True) as tdb_handle:
            self._traverse(tdb_handle, append_entries, state)

        return filter_list(state['output'], data['query-filters'], data['query-options'])

    @accepts(Dict(
        'tdb-batch-ops',
        Str('name', required=True),
        List('ops', required=True),
        Ref('tdb-options'),
    ))
    def batch_ops(self, data):
        """
        Perform a grouping of tdb operations under a transaction lock.
        """
        try:
            with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
                data = self._batch_ops(tdb_handle, data['ops'])
        except RuntimeError:
            self.logger.error('%s: failed batch operations, retrying: %s',
                              data['name'], data['ops'], exc_info=True)
            with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
                data = self._batch_ops(tdb_handle, data['ops'])

        return data

    @accepts(Dict(
        'tdb-wipe',
        Str('name', required=True),
        Ref('tdb-options'),
    ))
    def wipe(self, data):
        """
        Perform a tdb_wipe_all() operation on the specified tdb file.
        """
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._wipe(tdb_handle)

    @accepts(Dict(
        'tdb-flush',
        Str('name', required=True),
        Ref('tdb-options'),
    ))
    def flush(self, data):
        """
        Traverse the tdb file and delete all entries.
        """
        def remove_entries(tdb_key, tdb_data, state):
            self._rem(tdb_handle, tdb_key)
            return True

        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._traverse(tdb_handle, remove_entries, {})

    @accepts(Dict(
        'tdb-health',
        Str('name', required=True),
        Ref('tdb-options'),
    ))
    def health(self, data):
        with self.get_connection(data['name'], data['tdb-options'], True) as tdb_handle:
            return tdb_handle.health()

    @accepts()
    def show_handles(self):
        ret = {h['name']: h['options'] for h in self.handles.values()}
        return ret

    @private
    def close_cluster_handles(self):
        for entry in list(self.handles.values()):
            if not entry['options']['cluster']:
                continue

            with entry['lock']:
                if entry['handle_internal'] and entry['handle_internal'].validate_handle():
                    entry['handle_internal'].close()

    @private
    def close_sysdataset_handles(self):
        for name in list(self.handles.keys()):
            if not name.startswith(SYSDATASET_PATH):
                continue

            entry = self.handles[name]
            with entry['lock']:
                if entry['handle_internal'].validate_handle():
                    entry['handle_internal'].close()

    @private
    async def setup(self):
        for p in TDBPath:
            if p is TDBPath.CUSTOM:
                continue

            os.makedirs(p.value, mode=0o700, exist_ok=True)


async def setup(middleware):
    await middleware.call("tdb.setup")
