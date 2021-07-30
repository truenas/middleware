from middlewared.service import Service, private
from middlewared.schema import accepts, Bool, Dict, Ref, List, Str
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils import filter_list
from .connection import TDBMixin, TDBPath

import os
import json
import errno

from contextlib import closing


class TDBService(Service, TDBMixin):

    handles = {}

    class Config:
        private = True

    @private
    def get_connection(self, name, options):
        existing = self.handles.get('name')

        if existing:
            if options != existing['options']:
                raise CallError(f'{name}: Internal Error - tdb options mismatch', errno.EINVAL)
            if existing['handle']:
                return existing['handle']

        else:
            self.handles[name] = {'options': options.copy()}

        handle = self._get_handle(name, options)
        return handle

    @accepts(
        Str('name', required=True),
        Str('key', required=True),
        Dict('data', required=True, additional_attrs=True),
        Dict(
            'tdb-options',
            Str('backend', enum=['PERSISTENT', 'VOLATILE', 'INTERNAL'], default='PERSISTENT'),
            Str('tdb_type', enum=['BASIC', 'CRUD', 'CONFIG'], default='BASIC'),
            Bool('mmap', default=True),
            Bool('clustered', default=False),
        )
    )
    def store(self, name, tdb_key, data, options):
        handle = self.get_connection(name, options)
        tdb_val = json.dumps(data)

        with closing(handle) as tdb_handle:
            self._set(tdb_handle, tdb_key, tdb_val)

    @accepts(
        Str('name', required=True),
        Str('key', required=True),
        Dict(
            'tdb-options',
            Str('backend', enum=['PERSISTENT', 'VOLATILE', 'INTERNAL'], default='PERSISTENT'),
            Str('tdb_type', enum=['BASIC', 'CRUD', 'CONFIG'], default='BASIC'),
            Bool('mmap', default=True),
            Bool('clustered', default=False),
        )
    )
    def fetch(self, name, tdb_key, options):
        handle = self.get_connection(name, options)

        with closing(handle) as tdb_handle:
            tdb_val = self._get(tdb_handle, tdb_key)

        if tdb_val is None:
            raise MatchNotFound(tdb_key)

        data = json.loads(tdb_val)
        return data

    @accepts(
        Str('name', required=True),
        Ref('query-filters'),
        Ref('query-options'),
        Dict(
            'tdb_options',
            Str('backend', enum=['PERSISTENT', 'VOLATILE', 'INTERNAL'], default='PERSISTENT'),
            Str('tdb_type', enum=['BASIC', 'CRUD', 'CONFIG'], default='BASIC'),
            Bool('mmap', default=True),
            Bool('clustered', default=False),
        )
    )
    def entries(self, name, filters, options, tdb_options):
        def append_entries(tdb_key, tdb_data, outlist):
            if tdb_data is None:
                return True

            entry = json.loads(tdb_data)
            outlist.append({"key": tdb_key, "val": entry})
            return True

        output = []
        handle = self.get_connection(name, tdb_options)

        with closing(handle) as tdb_handle:
            self._traverse(tdb_handle, append_entries, output)

        return filter_list(output, filters, options)

    @accepts(
        Str('name', required=True),
        List('ops', required=True),
        Dict(
            'tdb-options',
            Str('backend', enum=['PERSISTENT', 'VOLATILE', 'INTERNAL'], default='PERSISTENT'),
            Str('tdb_type', enum=['BASIC', 'CRUD', 'CONFIG'], default='BASIC'),
            Bool('mmap', default=True),
        )
    )
    def batch_ops(self, name, ops, options):
        handle = self.get_connection(name, options)
        output = []

        with closing(handle) as tdb_handle:
            self._transaction(tdb_handle, 'START')
            try:
                for op in ops:
                    if op["action"] == "SET":
                        tdb_val = json.dumps(op["val"])
                        self._set(tdb_handle, op["key"], tdb_val)
                    if op["action"] == "DEL":
                        self._rem(tdb_handle, op["key"])
                    if op["action"] == "GET":
                        tdb_val = self._get(tdb_handle, op["key"])
                        output.append(json.loads(tdb_val))
                self._transaction(tdb_handle, "COMMIT")
            except Exception:
                self._transaction(tdb_handle, "CANCEL")
                raise

        return output

    @accepts(
        Str('name', required=True),
        Dict(
            'tdb_options',
            Str('backend', enum=['PERSISTENT', 'VOLATILE', 'INTERNAL'], default='PERSISTENT'),
            Str('tdb_type', enum=['BASIC', 'CRUD', 'CONFIG'], default='BASIC'),
            Bool('mmap', default=True),
            Bool('clustered', default=False),
        )
    )
    def wipe(self, name, options):
        handle = self.get_connection(name, options)
        with closing(handle) as tdb_handle:
            self._wipe(tdb_handle)

    @private
    async def setup(self):
        for p in TDBPath:
            os.makedirs(p.value, mode=0o700, exist_ok=True)


async def setup(middleware):
    await middleware.call("tdb.setup")
