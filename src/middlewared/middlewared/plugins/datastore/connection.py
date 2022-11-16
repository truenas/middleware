from concurrent.futures import ThreadPoolExecutor
import re

from sqlalchemy import create_engine

from middlewared.service import private, Service

from middlewared.plugins.config import FREENAS_DATABASE

thread_pool = ThreadPoolExecutor(1)


def regexp(expr, item):
    if item is None:
        return False

    reg = re.compile(expr, re.I)
    return reg.search(item) is not None


class DatastoreService(Service):

    class Config:
        private = True
        thread_pool = thread_pool

    engine = None
    connection = None

    @private
    def setup(self):
        if self.engine is not None:
            self.engine.dispose()

        if self.connection is not None:
            self.connection.close()

        self.engine = create_engine(f'sqlite:///{FREENAS_DATABASE}')

        self.connection = self.engine.connect()
        self.connection.connection.create_function("REGEXP", 2, regexp)

        self.connection.connection.execute("PRAGMA foreign_keys=ON")

        for row in self.connection.execute("PRAGMA foreign_key_check").fetchall():
            self.logger.warning("Deleting row %d in table %s that violates foreign key constraint on table %s",
                                row.rowid, row.table, row.parent)
            self.connection.execute(f"DELETE FROM {row.table} WHERE rowid = {row.rowid}")

        self.connection.connection.execute("VACUUM")

    @private
    def execute(self, *args):
        return self.connection.execute(*args)

    @private
    def execute_write(self, stmt, options=None):
        options = options or {}
        options.setdefault('ha_sync', True)
        options.setdefault('return_last_insert_rowid', False)

        compiled = stmt.compile(self.engine)

        sql = compiled.string
        binds = []
        for param in compiled.positiontup:
            bind = compiled.binds[param]
            value = bind.value
            bind_processor = compiled.binds[param].type.bind_processor(self.engine.dialect)
            if bind_processor:
                binds.append(bind_processor(value))
            else:
                binds.append(value)

        result = self.connection.execute(sql, binds)

        self.middleware.call_hook_inline("datastore.post_execute_write", sql, binds, options)

        if options['return_last_insert_rowid']:
            return self.fetchall("SELECT last_insert_rowid()")[0][0]

        return result

    @private
    def fetchall(self, query, params=None):
        cursor = self.connection.execute(query, params or [])
        try:
            return cursor.fetchall()
        finally:
            cursor.close()
