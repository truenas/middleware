from concurrent.futures import ThreadPoolExecutor
import re
import shutil
import time

from sqlalchemy import create_engine, text

from middlewared.service import private, Service

from middlewared.utils.db import FREENAS_DATABASE

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
    def handle_constraint_violation(self, row, journal):
        self.logger.warning("Row %d in table %s violates foreign key constraint on table %s.",
                            row.rowid, row.table, row.parent)

        self.logger.warning("Deleting row %d from table %s.", row.rowid, row.table)
        op = f"DELETE FROM {row.table} WHERE rowid = {row.rowid}"
        self.connection.execute(text(op))
        journal.write(f'{op}\n')

    @private
    def setup(self):
        # In SQLAlchemy 2.0, we must close connections before disposing the engine
        # to avoid "Cannot operate on a closed database" errors
        if self.connection is not None:
            self.connection.close()

        if self.engine is not None:
            self.engine.dispose()

        self.engine = create_engine(f'sqlite:///{FREENAS_DATABASE}')
        self.connection = self.engine.connect()
        self.connection = self.connection.execution_options(isolation_level="AUTOCOMMIT")
        self.connection.connection.create_function("REGEXP", 2, regexp)
        self.connection.connection.execute("PRAGMA foreign_keys=ON")

        if constraint_violations := self.connection.execute(text("PRAGMA foreign_key_check")).fetchall():
            ts = int(time.time())
            shutil.copy(FREENAS_DATABASE, f'{FREENAS_DATABASE}_{ts}.bak')

            with open(f'{FREENAS_DATABASE}_{ts}_journal.txt', 'w') as f:
                for row in constraint_violations:
                    self.handle_constraint_violation(row, f)

        self.connection.connection.execute("VACUUM")

    @private
    def execute(self, query, *params):
        if len(params) == 1 and isinstance(params[0], (list, tuple)):
            params = tuple(params[0])

        return self.connection.exec_driver_sql(query, params)

    @private
    def execute_write(self, stmt, options=None):
        options = options or {}
        options.setdefault('ha_sync', True)
        options.setdefault('return_last_insert_rowid', False)

        compiled = stmt.compile(self.engine, compile_kwargs={"render_postcompile": True})

        param_to_bind = {}
        if compiled._post_compile_expanded_state:
            for bind, parameters in compiled._post_compile_expanded_state.parameter_expansion.items():
                for parameter in parameters:
                    param_to_bind[parameter] = bind

        sql = compiled.string
        binds = []
        for param in compiled.positiontup:
            if compiled._post_compile_expanded_state:
                bind = compiled.binds[param_to_bind[param]]
                value = compiled._post_compile_expanded_state.parameters[param]
            else:
                bind = compiled.binds[param]
                value = bind.value

            bind_processor = bind.type.bind_processor(self.engine.dialect)
            if bind_processor:
                binds.append(bind_processor(value))
            else:
                binds.append(value)

        result = self.connection.exec_driver_sql(sql, tuple(binds))

        self.middleware.call_hook_inline("datastore.post_execute_write", sql, binds, options)

        if options['return_last_insert_rowid']:
            return self.connection.execute(text("SELECT last_insert_rowid() as rowid")).scalar_one()

        return result

    @private
    def fetchall(self, query, params=None):
        cursor = self.connection.execute(text(query) if isinstance(query, str) else query, params or {})
        try:
            return list(cursor.mappings())
        finally:
            cursor.close()
