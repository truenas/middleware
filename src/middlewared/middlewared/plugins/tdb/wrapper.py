import os
import tdb
import ctdb
import enum
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
    full_path = None
    opath_fd = -1

    def close(self):
        self.hdl.close()
        os.close(self.opath_fd)

    def is_clustered(self):
        return False

    def validate_handle(self):
        if not os.path.exists(f'/proc/self/fd/{self.opath_fd}'):
            return False
        # if file has been renamed or deleted from under us, readlink will show different path

        return os.readlink(f'/proc/self/fd/{self.opath_fd}') == self.full_path

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
            tdb_val = val
        else:
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

    def __init__(self, name, options, logger):
        self.name = str(name)
        tdb_type = options.get('backend', 'PERSISTENT')
        tdb_flags = tdb.DEFAULT
        open_flags = os.O_CREAT | os.O_RDWR
        open_mode = 0o600

        if tdb_type != 'CUSTOM':
            name = f'{TDBPath[tdb_type].value}/{name}.tdb'

        self.full_path = name
        self.hdl = tdb.Tdb(name, 0, tdb_flags, open_flags, open_mode)
        self.opath_fd = os.open(name, os.O_PATH)
        self.options = copy.deepcopy(options)
        super().__init__()


class CTDBWrap(object):

    dbid = None
    options = {}
    cached_data = None
    last_read = 0
    hdl = None
    skip_trans = False
    logger = None

    def is_clustered(self):
        return True

    def __db_is_persistent(self):
        return True if self.hdl.db_flags & ctdb.DB_PERSISTENT else False

    def __init__(self, name, dbid, options, logger):
        self.name = name
        self.dbid = hex(dbid)
        self.options = copy.deepcopy(options)
        self.hdl = ctdb.Ctdb(ctdb.Client(), self.dbid, os.O_CREAT)
        self.logger = logger
        tdb_type = options.get('backend', 'PERSISTENT')
        if tdb_type == 'PERSISTENT':
            self.hdl.attach(ctdb.DB_PERSISTENT)
        else:
            self.hdl

        super().__init__()

    def validate_handle(self):
        return self.hdl is not None

    def close(self):
        # Closing last reference to pyctdb_client_ctx will
        # TALLOC_FREE() any talloc'ed memory under the handle.
        del(self.hdl)
        self.hdl = None
        return

    def __persistent_fetch(self, tdb_key):
        if not self.skip_trans:
            self.hdl.start_transaction(True)
        db_entry = self.hdl.fetch(tdb_key)
        if not self.skip_trans:
            self.hdl.cancel_transaction()
        return db_entry.value

    def __volatile_fetch(self, tdb_key):
        db_entry = self.hdl.fetch(tdb_key)
        db_entry.unlock()
        return db_entry.value

    def get(self, key):
        tdb_key = key.encode()

        if self.options['data_type'] == 'BYTES':
            tdb_key += b"\x00"

        if self.__db_is_persistent():
            tdb_val = self.__persistent_fetch(tdb_key)
        else:
            tdb_val = self.__volatile_fetch(tdb_key)

        if self.options['data_type'] == 'BYTES':
            return tdb_val

        if tdb_val is not None:
            tdb_val = tdb_val.decode()

        return tdb_val

    def __persistent_store(self, key, value):
        if not self.skip_trans:
            self.hdl.start_transaction(False)

        self.hdl.store(key, value)
        if not self.skip_trans:
            self.hdl.commit_transaction()

        return

    def __volatile_store(self, key, value):

        db_entry = self.hdl.fetch(key)
        db_entry.store(value)
        db_entry.unlock()
        return

    def store(self, key, val):
        tdb_key = key.encode()
        if self.options['data_type'] == 'BYTES':
            tdb_key += b"\x00"

        tdb_val = val.encode()
        if self.__db_is_persistent():
            self.__persistent_store(tdb_key, tdb_val)
        else:
            self.__volatile_store(tdb_key, tdb_val)

        return

    def __persistent_delete(self, key):
        if not self.skip_trans:
            self.hdl.start_transaction(False)

        self.hdl.delete(key)
        if not self.skip_trans:
            self.hdl.commit_transaction()

        return

    def __volatile_delete(self, key):
        db_entry = self.hdl.fetch(key)
        db_entry.delete()
        db_entry.unlock()
        return

    def delete(self, key):
        """
        remove a single entry from tdb file.
        """
        tdb_key = key.encode()
        if self.options['data_type'] == 'BYTES':
            tdb_key += b"\x00"

        if self.__db_is_persistent():
            self.__persistent_delete(tdb_key)
        else:
            self.__volatile_delete(tdb_key)
        return

    def clear(self):
        w = run(['ctdb', 'wipedb', self.dbid], capture_output=True)
        if w.returncode != 0:
            raise CallError(f"{self.dbid}: failed to w: {w.stderr.decode()}")

        return

    def __collect_keys_cb(dbentry, keys_out):
        keys_out.append(dbentry.key)

    def keys(self):
        keys = []
        self.hdl.traverse(self.__collect_keys_cb, keys)
        return keys

    def batch_op(self, ops):
        output = []
        self.hdl.start_transaction(False)
        self.skip_trans = True
        for op in ops:
            if op["action"] == "SET":
                tdb_val = json.dumps(op["val"])
                self.store(op["key"], tdb_val)
            if op["action"] == "DEL":
                self.delete(op["key"])
            if op["action"] == "GET":
                tdb_val = self.get(op["key"])
                output.append(json.loads(tdb_val))

        self.hdl.commit_transaction()
        self.skip_trans = False

        return output

    def traverse(self, fn, private_data):
        def _traverse_cb(dbentry, state):
            fn, private_data = state
            return fn(dbentry.key.decode(), dbentry.value.decode(), private_data)

        return self.hdl.traverse(_traverse_cb, (fn, private_data), False)
