from middlewared.plugins.sysdataset import SYSDATASET_PATH
from middlewared.service import Service, private
from middlewared.schema import accepts, Bool, Dict, Ref, List, Str, Int
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils import filter_list
from .connection import TDBMixin
from .schema import SchemaMixin
from .wrapper import TDBPath

import ctdb
import errno
import json
import os
import threading

from base64 import b64encode, b64decode
from contextlib import contextmanager


class TDBService(Service, TDBMixin, SchemaMixin):

    handles = {}

    class Config:
        private = True

    @private
    def validate_tdb_options(self, name, options):
        if options['service_version']['major'] > 0 or options['service_version']['minor'] > 0:
            if options['tdb_type'] == 'BASIC':
                raise CallError(
                    f"{name}: BASIC tdb types do not support versioning",
                    errno.EINVAL
                )

        if not options['cluster']:
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
    def get_connection(self, name, options):
        self.validate_tdb_options(name, options)

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
            Str('tdb_type', enum=['BASIC', 'CRUD', 'CONFIG'], default='BASIC'),
            Str('data_type', enum=['JSON', 'STRING', 'BYTES'], default='JSON'),
            Bool('cluster', default=False),
            Int('read_backoff', default=0),
            Dict('service_version', Int('major', default=0), Int('minor', default=0)),
            register=True
        )
    ))
    def store(self, data):
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
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
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
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._rem(tdb_handle, data['key'])

    @accepts(Dict(
        Str('name', required=True),
        Ref('query-filters'),
        Ref('query-options'),
        Ref('tdb-options'),
    ))
    def entries(self, data):
        def append_entries(tdb_key, tdb_data, state):
            if tdb_data is None:
                return True

            if state['data_type'] == 'JSON':
                entry = json.loads(tdb_data)
            elif state['data_type'] == 'STRING':
                entry = tdb_data
            elif state['data_type'] == 'BYTES':
                entry = b64encode(tdb_data)

            state['output'].append({"key": tdb_key, "val": entry})
            return True

        state = {
            'output': [],
            'data_type': data['tdb-options']['data_type']
        }

        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._traverse(tdb_handle, append_entries, state)

        return filter_list(state['output'], data['query-filters'], data['query-options'])

    @accepts(Dict(
        'tdb-batch-ops',
        Str('name', required=True),
        List('ops', required=True),
        Ref('tdb-options'),
    ))
    def batch_ops(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            data = self._batch_ops(tdb_handle, data['ops'])

        return data

    @accepts(Dict(
        'tdb-wipe',
        Str('name', required=True),
        Ref('tdb-options'),
    ))
    def wipe(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._wipe(tdb_handle)

    @accepts(Dict(
        'tdb-config-config',
        Str('name', required=True),
        Ref('tdb-options'),
    ))
    def config(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            data = self._config_config(tdb_handle)

        return data

    @accepts(Dict(
        'tdb-config-update',
        Str('name', required=True),
        Dict('payload', additional_attrs=True),
        Ref('tdb-options'),
    ))
    def config_update(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._config_update(tdb_handle, data['payload'])

        return

    @accepts(Dict(
        'tdb-crud-create',
        Str('name', required=True),
        Dict('payload', additional_attrs=True),
        Ref('tdb-options'),
    ))
    def create(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            id = self._create(tdb_handle, data['payload'])

        return id

    @accepts(Dict(
        'tdb-crud-query',
        Str('name', required=True),
        Ref('query-filters'),
        Ref('query-options'),
        Ref('tdb-options'),
    ))
    def query(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            data = self._query(tdb_handle, data['query-filters'], data['query-options'])

        return data

    @accepts(Dict(
        'tdb-crud-update',
        Str('name', required=True),
        Int('id', required=True),
        Dict('payload', additional_attrs=True),
        Ref('tdb-options'),
    ))
    def update(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            id = self._update(tdb_handle, data['id'], data['payload'])

        return id

    @accepts(Dict(
        'tdb-crud-delete',
        Str('name', required=True),
        Int('id', required=True),
        Ref('tdb-options'),
    ))
    def delete(self, data):
        with self.get_connection(data['name'], data['tdb-options']) as tdb_handle:
            self._delete(tdb_handle, data['id'])

        return

    @accepts(Dict(
        'tdb-upgrade',
        Str('name', required=True),
        Ref('tdb-options'),
    ))
    def apply_upgrades(self, data):
        raise NotImplementedError

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
                if entry['handle_internal'].validate_handle():
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
