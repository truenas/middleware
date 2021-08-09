from .wrapper import CTDBWrap, TDBWrap


class TDBMixin:
    def _get_handle(self, name, dbid, options):
        if options['cluster']:
            return CTDBWrap(name, dbid, options)

        return TDBWrap(name, options)

    def _close_handle(self, tdb_handle):
        tdb_handle.close()

    def _get(self, tdb_handle, key):
        tdb_val = tdb_handle.get(key)
        return tdb_val if tdb_val else None

    def _set(self, tdb_handle, key, val):
        tdb_handle.store(key, val)

    def _rem(self, tdb_handle, key):
        tdb_handle.delete(key)

    def _traverse(self, tdb_handle, fn, private_data):
        rv = tdb_handle.traverse(fn, private_data)
        return rv

    def _wipe(self, tdb_handle):
        tdb_handle.clear()

    def _entries(self, tdb_handle):
        entries = tdb_handle.entries()
        return entries

    def _batch_ops(self, tdb_handle, ops):
        result = tdb_handle.batch_op(ops)
        return result
