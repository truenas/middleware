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

        if row.table == "directoryservice_idmap_domain" and row.rowid <= 5 and row.parent == "system_certificate":
            """
            In commit 5265c8c49f8 a migration was written to use AUTOINCREMENT to ensure id uniqueness.
            In commit 85f5b97ec9a the aforementioned migration was modified to also fix potential constraint
            violation in this field.

            Since there was a gap between these two commits, it is impossible that the original
            migration without the subsequent revision and therefore the user's DB still contains the original
            constraint violation. This table entry is critical to the proper function of the AD
            plugin and since it is user-configurable, deletion cannot be repaired without manual
            intervention.
            """
            self.logger.warning("Removing certificate id for default idmap table entry.")
            self.connection.execute(text(
                f"UPDATE {row.table} SET idmap_domain_certificate_id = NULL WHERE rowid = {row.rowid}"
            ))
            return

        self.logger.warning("Deleting row %d from table %s.", row.rowid, row.table)
        op = f"DELETE FROM {row.table} WHERE rowid = {row.rowid}"
        self.connection.execute(text(op))
        journal.write(f'{op}\n')

    @private
    def setup(self):
        if self.engine is not None:
            self.engine.dispose()

        if self.connection is not None:
            self.connection.close()

        self.engine = create_engine(f'sqlite:///{FREENAS_DATABASE}', isolation_level='AUTOCOMMIT')

        self.connection = self.engine.connect()
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
    def execute(self, *args):
        args = list(args)
        if args and isinstance(args[0], str):
            args[0] = text(args[0])
        return self.connection.execute(*args)

    @private
    def execute_write(self, stmt, options=None):
        options = options or {}
        options.setdefault('ha_sync', True)
        options.setdefault('return_last_insert_rowid', False)

        compiled = stmt.compile(self.engine, compile_kwargs={"render_postcompile": True})
        sql = compiled.string
        params = compiled.params or {}
        result = self.connection.execute(stmt)

        self.middleware.call_hook_inline("datastore.post_execute_write", sql, params, options)

        if options['return_last_insert_rowid']:
            return self.fetchall("SELECT last_insert_rowid()")[0][0]

        return result

    @private
    def fetchall(self, query, params=None):
        cursor = self.connection.execute(text(query) if isinstance(query, str) else query, params or {})
        try:
            return cursor.fetchall()
        finally:
            cursor.close()
