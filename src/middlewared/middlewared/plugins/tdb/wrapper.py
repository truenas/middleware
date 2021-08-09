import os
import tdb
import enum
import errno
import json
import copy
from subprocess import run
from middlewared.service_exception import CallError


class TDBPath(enum.Enum):
    VOLATILE = '/var/run/tdb/volatile'
    PERSISTENT = '/root/tdb/persistent'
    CUSTOM = ''


class TDBWrap(object):
    hdl = None
    name = None
    options = {}
    cached_data = None
    last_read = 0

    def close(self):
        self.hdl.close()

    def is_clustered(self):
        return False

    def get(self, key):
        tdb_key = key.encode()
        if self.options['data_type'] == 'BYTES':
            tdb_key += b"\x00"

        tdb_val = self.hdl.get(tdb_key)
        if self.options['data_type'] == 'BYTES':
            return tdb_val

        if tdb_val is not None:
            tdb_val = tdb_val.decode()

        return tdb_val

    def store(self, key, val):
        tdb_key = key.encode()
        if self.options['data_type'] == 'BYTES':
            tdb_key += b"\x00"

        tdb_val = val.encode()

        self.hdl.store(tdb_key, tdb_val)

    def delete(self, key):
        tdb_key = key.encode()
        if self.options['data_type'] == 'BYTES':
            tdb_key += b"\x00"

        self.hdl.delete(tdb_key)

    def clear(self):
        self.hdl.clear()

    def traverse(self, fn, private_data):
        ok = True
        for i in self.hdl.keys():
            tdb_key = i.decode()
            tdb_val = self.get(tdb_key)
            ok = fn(tdb_key, tdb_val, private_data)
            if not ok:
                break

        return ok

    def batch_op(self, ops):
        output = []
        self.hdl.transaction_start()
        try:
            for op in ops:
                if op["action"] == "SET":
                    tdb_val = json.dumps(op["val"])
                    self.store(op["key"], tdb_val)
                if op["action"] == "DEL":
                    self.delete(op["key"])
                if op["action"] == "GET":
                    tdb_val = self.get(op["key"])
                    output.append(json.loads(tdb_val))

            self.hdl.transaction_commit()
        except Exception:
            self.hdl.transaction_cancel()
            raise

        return output

    def __init__(self, name, options):
        self.name = str(name)
        tdb_type = options.get('backend', 'PERSISTENT')
        tdb_flags = tdb.DEFAULT
        open_flags = os.O_CREAT | os.O_RDWR
        open_mode = 0o600

        if tdb_type != 'CUSTOM':
            name = f'{TDBPath[tdb_type].value}/{name}.tdb'

        self.hdl = tdb.Tdb(name, 0, tdb_flags, open_flags, open_mode)
        self.options = copy.deepcopy(options)
        super().__init__()


class CTDBWrap(object):

    dbid = None
    options = {}
    cached_data = None
    last_read = 0

    def is_clustered(self):
        return True

    def __init__(self, name, dbid, options, **kwargs):
        self.name = name
        self.dbid = dbid
        self.options = copy.deepcopy(options)
        super().__init__()

    def close(self):
        # no-op to keep closing context manager happy
        return

    def get(self, tdb_key):
        cmd = ['ctdb', 'pfetch', self.dbid, tdb_key]
        tdb_get = run(cmd, capture_output=True)
        if tdb_get.returncode != 0:
            raise CallError(f"{tdb_key}: failed to fetch: {tdb_get.stderr.decode()}")

        tdb_val = tdb_get.stdout.decode().strip()
        if not tdb_val:
            return None

        return tdb_val

    def store(self, key, val):
        tdb_set = run(['ctdb', 'pstore', self.dbid, key, val], capture_output=True)
        if tdb_set.returncode != 0:
            raise CallError(f"{key}: failed to set to {val}: {tdb_set.stderr.decode()}")

        return

    def delete(self, key):
        """
        remove a single entry from tdb file.
        """
        tdb_del = run(['ctdb', 'pdelete', self.dbid, key], capture_output=True)
        if tdb_del.returncode != 0:
            raise CallError(f"{key}: failed to delete: {tdb_del.stderr.decode()}")
            return None

        return

    def clear(self):
        w = run(['ctdb', 'wipedb', self.dbid], capture_output=True)
        if w.returncode != 0:
            raise CallError(f"{self.dbid}: failed to w: {w.stderr.decode()}")

        return

    def keys(self):
        trv = run(['ctdb', 'catdb_json', self.dbid], capture_output=True)
        if trv.returncode != 0:
            raise CallError(f"{self.dbid}: failed to get_keys: {trv.stderr.decode()}")

        tdb_entries = json.loads(trv.stdout.decode())
        keys = [x['key'] for x in tdb_entries['data']]
        return keys

    def batch_op(self, ops):
        input = []
        for op in ops:
            to_add = None
            if op['action'] == 'GET':
                to_add = {
                    "action": "FETCH",
                    "key": op["key"],
                }
            elif op['action'] == 'SET':
                to_add = {
                    "action": "STORE",
                    "key": op["key"],
                    "val": op["val"],
                }
            elif op['action'] == 'DEL':
                to_add = {
                    "action": 'DELETE',
                    "key": op["key"],
                }

            if to_add is None:
                raise CallError(f'{op["action"]}: unknown action', errno.EINVAL)

            input.append(to_add)

        payload = json.dumps(input)
        op_run = run(
            ['ctdb', 'pbatch', self.dbid, '-'],
            check=False, capture_output=True, encoding='utf8', input=payload
        )
        if op_run.returncode != 0:
            raise CallError(f'{self.dbid}: failed to perform batch operation: {op_run.stderr}')

        if op_run.stdout:
            output = json.loads(op_run.stdout.strip())
        else:
            output = []

        return output

    def traverse(self, fn, private_data):
        ok = True
        trv = run(['ctdb', 'catdb_json', self.dbid], capture_output=True)
        if trv.returncode != 0:
            raise CallError(f"{self.dbid}: failed to traverse: {trv.stderr.decode()}")

        tdb_entries = json.loads(trv.stdout.decode())
        for i in tdb_entries['data']:
            ok = fn(i['key'], i['val'], private_data)
            if not ok:
                break

        return ok
