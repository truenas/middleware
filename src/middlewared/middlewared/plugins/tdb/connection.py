import tdb
import os
import enum


class TDBPath(enum.Enum):
    VOLATILE = '/var/run/tdb/volatile'
    PERSISTENT = '/root/tdb/persistent'


class TDBMixin:
    def _get_handle(self, name, options):
        tdb_type = options.get('backend', 'PERSISTENT')
        tdb_flags = tdb.DEFAULT
        open_flags = os.O_CREAT | os.O_RDWR
        open_mode = 0o600

        if tdb_type == 'INTERNAL':
            tdb_flags |= tdb.INTERNAL

        if not options.get('mmap', True):
            tdb_flags |= tdb.NOMMAP

        if not tdb_flags & tdb.INTERNAL:
            name = f'{TDBPath[tdb_type].value}/{name}.tdb'

        handle = tdb.Tdb(name, 0, tdb_flags, open_flags, open_mode)
        return handle

    def _close_handle(self, tdb_handle):
        tdb_handle.close()

    def _get(self, tdb_handle, key):
        tdb_key = key.encode()
        tdb_val = tdb_handle.get(tdb_key)
        return tdb_val.decode() if tdb_val else None

    def _set(self, tdb_handle, key, val):
        tdb_key = key.encode()
        tdb_val = val.encode()
        tdb_handle.store(tdb_key, tdb_val)

    def _rem(self, tdb_handle, key):
        tdb_key = key.encode()
        tdb_handle.delete(tdb_key)

    def _traverse(self, tdb_handle, fn, private_data):
        ok = True
        for i in tdb_handle.keys():
            tdb_key = i.decode()
            tdb_val = self._get(tdb_handle, tdb_key)
            ok = fn(tdb_key, tdb_val, private_data)
            if not ok:
                break

        return ok

    def _wipe(self, tdb_handle):
        tdb_handle.clear()

    def _transaction(self, tdb_handle, verb):
        if verb == 'START':
            tdb_handle.transaction_start()
        elif verb == 'CANCEL':
            tdb_handle.transaction_cancel()
        elif verb == 'COMMIT':
            tdb_handle.transaction_commit()
