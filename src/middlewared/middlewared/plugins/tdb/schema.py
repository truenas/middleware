from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils import filter_list

import errno
import json
import time
import copy


class SchemaMixin:

    def assert_tdb_type(self, tdb_type, expected):
        if tdb_type in expected:
            return

        raise CallError(f'{tdb_type}: operation not supported on tdb handle', errno.ENOTSUP)

    def _service_version(self, tdb_handle):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CRUD', 'CONFIG'])

        v = tdb_handle.get("service_version")
        if v is None:
            return None

        maj, min = v.split(".")
        return {"major": int(maj), "minor": int(min)}

    def _version_check(self, tdb_handle, new):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CRUD', 'CONFIG'])

        local_version = self._service_version(tdb_handle)
        if local_version is None:
            tdb_handle.store("service_version", f'{new["major"]}.{new["minor"]}')
            return

        if new == local_version:
            return

        raise ValueError

    def _tdb_entries(self, tdb_handle):
        def tdb_to_list(tdb_key, tdb_val, data):
            if tdb_key == "hwm":
                data['hwm'] = int(tdb_val)
                return True

            if not tdb_key.startswith(data['schema']):
                return True

            entry = {"id": int(tdb_key[data["prefix_len"]:])}
            tdb_json = json.loads(tdb_val)
            entry.update(tdb_json)

            data['entries'].append(entry)
            data['by_id'][entry['id']] = entry
            return True

        state = {
            "schema": tdb_handle.name,
            "prefix_len": len(tdb_handle.name) + 1,
            "hwm": 1,
            "entries": [],
            "by_id": {}
        }

        tdb_handle.traverse(tdb_to_list, state)

        return state

    def _config_config(self, tdb_handle):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CONFIG'])

        now = time.monotonic()
        if tdb_handle.last_read + tdb_handle.options['read_backoff'] > now:
            cache_data = copy.deepcopy(tdb_handle.cached_data)
            return cache_data

        vers = self._service_version(tdb_handle)
        if not vers:
            vers = tdb_handle.options['service_version'].copy()

        tdb_val = tdb_handle.get(tdb_handle.name)
        output = json.loads(tdb_val) if tdb_val else None

        if output:
            tdb_handle.cached_data = {
                'version': vers.copy(),
                'data': copy.deepcopy(output)
            }

            tdb_handle.last_read = now

        return {"version": vers, "data": output}

    def _config_update(self, tdb_handle, payload):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CONFIG'])

        vers = payload['version']
        data = payload['data']

        self._version_check(tdb_handle, vers)

        tdb_val = json.dumps(data)
        tdb_handle.last_read = 0
        tdb_handle.store(tdb_handle.name, tdb_val)

    def _query(self, tdb_handle, filters, options):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CRUD'])

        now = time.monotonic()
        if tdb_handle.last_read + tdb_handle.options['read_backoff'] > now:
            cache_data = copy.deepcopy(tdb_handle.cached_data)
            filtered = filter_list(cache_data['data'], filters, options)
            return {"version": cache_data["version"], "data": filtered}

        vers = self._service_version(tdb_handle)
        if vers is None:
            vers = tdb_handle.options['service_version'].copy()

        state = self._tdb_entries(tdb_handle)

        if state['entries']:
            tdb_handle.cached_data = {
                'version': vers.copy(),
                'data': copy.deepcopy(state['entries'])
            }
            tdb_handle.last_read = now

        res = filter_list(state['entries'], filters, options)
        return {"version": vers, "data": res}

    def _create(self, tdb_handle, payload):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CRUD'])

        vers = payload['version']
        data = payload['data']

        self._version_check(tdb_handle, vers)
        state = self._tdb_entries(tdb_handle)

        id = state["hwm"] + 1
        tdb_key = f'{tdb_handle.name}_{id}'

        ops = [
            {"action": "SET", "key": tdb_key, "val": data},
            {"action": "SET", "key": "hwm", "val": id}
        ]
        tdb_handle.batch_op(ops)
        tdb_handle.last_read = 0

        return id

    def _update(self, tdb_handle, id, payload):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CRUD'])

        tdb_key = f'{tdb_handle.name}_{id}'
        vers = payload['version']
        new = payload['data']

        self._version_check(tdb_handle, vers)
        state = self._tdb_entries(tdb_handle)

        old = state['by_id'].get(id)
        if not old:
            raise MatchNotFound()

        old.update(new)
        old_id = old.pop('id')
        tdb_val = json.dumps(old)
        tdb_handle.store(tdb_key, tdb_val)
        tdb_handle.last_read = 0
        return old_id

    def _delete(self, tdb_handle, id):
        self.assert_tdb_type(tdb_handle.options['tdb_type'], ['CRUD'])

        tdb_key = f'{tdb_handle.name}_{id}'

        state = self._tdb_entries(tdb_handle)
        if not state['by_id'].get(id):
            raise MatchNotFound()

        tdb_handle.delete(tdb_key)
        tdb_handle.last_read = 0
        return
