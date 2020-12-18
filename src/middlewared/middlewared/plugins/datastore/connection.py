from concurrent.futures import ThreadPoolExecutor
import re

from sqlalchemy import create_engine

from middlewared.service import private, Service

from middlewared.plugins.config import FREENAS_DATABASE


def regexp(expr, item):
    if item is None:
        return False

    reg = re.compile(expr, re.I)
    return reg.search(item) is not None


class DatastoreService(Service):

    class Config:
        private = True

    thread_pool = ThreadPoolExecutor(1)

    engine = None
    connection = None

    @private
    async def setup(self):
        await self.middleware.run_in_executor(self.thread_pool, self._setup)

    def _setup(self):
        if self.engine is not None:
            self.engine.dispose()

        if self.connection is not None:
            self.connection.close()

        self.engine = create_engine(f'sqlite:///{FREENAS_DATABASE}')

        self.connection = self.engine.connect()
        self.connection.connection.create_function("REGEXP", 2, regexp)
        self.connection.connection.execute("PRAGMA foreign_keys=ON")

    @private
    async def execute(self, *args):
        return await self.middleware.run_in_executor(self.thread_pool, self.connection.execute, *args)

    @private
    async def execute_write(self, stmt, return_last_insert_rowid=False):
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

        return await self.middleware.run_in_executor(self.thread_pool, self._execute_write, sql, binds,
                                                     return_last_insert_rowid)

    def _execute_write(self, sql, binds, return_last_insert_rowid):
        result = self.connection.execute(sql, binds)

        self.middleware.call_hook_inline("datastore.post_execute_write", sql, binds)

        if return_last_insert_rowid:
            return self._fetchall("SELECT last_insert_rowid()")[0][0]

        return result

    @private
    async def fetchall(self, *args):
        return await self.middleware.run_in_executor(self.thread_pool, self._fetchall, *args)

    def _fetchall(self, query, params=None):
        cursor = self.connection.execute(query, params or [])
        try:
            return cursor.fetchall()
        finally:
            cursor.close()
