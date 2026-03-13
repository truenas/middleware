import re
import shutil
import threading
import time
from os import getpid

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool

from middlewared.service import private, Service
from middlewared.service_exception import CallError

from middlewared.utils.db import FREENAS_DATABASE

_tls = threading.local()


def regexp(expr, item):
    if item is None:
        return False

    reg = re.compile(expr, re.I)
    return reg.search(item) is not None


def _on_db_connect(dbapi_conn, _):
    dbapi_conn.create_function('REGEXP', 2, regexp)
    dbapi_conn.execute('PRAGMA foreign_keys=ON')


class DatastoreService(Service):

    class Config:
        private = True

    engine = None
    write_lock = threading.Lock()
    _generation = 0
    _main_pid = None

    def _get_conn(self):
        """Return the thread-local SQLite connection for the current generation.

        Creates a fresh connection when either no connection exists for this thread
        or the global generation counter has advanced past what the thread last saw.
        The typical trigger for a generation bump is a new database being uploaded,
        after which setup() disposes the old engine and increments the counter so
        every thread transparently reconnects on its next access.
        The stale connection is closed before the new one is opened.
        """
        gen = self._generation
        if getattr(_tls, 'db_generation', -1) != gen:
            if (old := getattr(_tls, 'db_conn', None)) is not None:
                try:
                    old.close()
                except Exception:
                    pass
            _tls.db_conn = self.engine.connect().execution_options(isolation_level='AUTOCOMMIT')
            _tls.db_generation = gen

        return _tls.db_conn

    @private
    def handle_constraint_violation(self, conn, row, journal):
        """Log and remove a row that violates a foreign key constraint.

        The offending DELETE statement is also appended to `journal` so that the
        corrective actions taken at startup can be audited after the fact.
        """
        self.logger.warning("Row %d in table %s violates foreign key constraint on table %s.",
                            row.rowid, row.table, row.parent)

        self.logger.warning("Deleting row %d from table %s.", row.rowid, row.table)
        op = f"DELETE FROM {row.table} WHERE rowid = {row.rowid}"
        conn.execute(text(op))
        journal.write(f'{op}\n')

    @private
    def setup(self):
        """Initialise (or re-initialise) the SQLite engine.

        Disposes any existing engine, creates a fresh one, bumps the generation
        counter so all threads obtain new connections on their next access, records
        the current PID to guard against forked-child writes, repairs any
        foreign-key violations, and runs VACUUM.
        """
        if self.engine is not None:
            self.engine.dispose()

        # We're using a NullPool here because we're manually managing per-thread connections
        # This is because in regular workflows we expect the database to get completely replaced
        # (like during config uploads) and we need to track the "generation" of database to
        # invalidate our per-thread connection.
        self.engine = create_engine(
            f'sqlite:///{FREENAS_DATABASE}',
            connect_args={'check_same_thread': False},
            poolclass=NullPool,
        )

        event.listen(self.engine, 'connect', _on_db_connect)

        self._generation += 1
        self._main_pid = getpid()
        conn = self._get_conn()

        if constraint_violations := conn.execute(text('PRAGMA foreign_key_check')).fetchall():
            ts = int(time.time())
            shutil.copy(FREENAS_DATABASE, f'{FREENAS_DATABASE}_{ts}.bak')

            with open(f'{FREENAS_DATABASE}_{ts}_journal.txt', 'w') as f:
                for row in constraint_violations:
                    self.handle_constraint_violation(conn, row, f)

        conn.connection.execute('VACUUM')

    def _check_main_pid(self):
        """Raise CallError if called from a process other than the one that ran setup().

        Forked child processes must not write to the database because writes in the
        child bypass the main process write_lock and the post_execute_write hook,
        breaking the serialization guarantees that update hooks depend on.
        """
        if getpid() != self._main_pid:
            raise CallError('Datastore writes are not permitted from a forked child process')

    @private
    def execute(self, query, *params):
        """Execute a raw SQL write statement under the write lock.

        Accepts either positional parameters or a single list/tuple of parameters.
        Raises CallError if called from a forked child process.
        """
        self._check_main_pid()
        if len(params) == 1 and isinstance(params[0], (list, tuple)):
            params = tuple(params[0])

        with self.write_lock:
            self._get_conn().exec_driver_sql(query, params)

    @private
    def execute_write(self, stmt, options=None):
        """Compile and execute a SQLAlchemy DML statement under the write lock.

        Handles bind-parameter expansion for IN clauses and type-processor coercion.
        When `return_last_insert_rowid` is set in options the integer row ID of the
        inserted row is returned; otherwise the raw DBAPI result is returned.
        Raises CallError if called from a forked child process.

        After each successful write, fires the `datastore.post_execute_write` hook
        **while still holding the write_lock**. The hook is registered as inline so
        it runs synchronously on this thread. On HA systems this is where SQL
        replication to the backup controller happens; holding the lock during the
        hook call is intentional — it prevents any other write from reaching the
        local database before the same SQL has been forwarded to the remote, avoiding
        replication race conditions. Consequently, anything invoked from within that
        hook must not attempt to call execute() or execute_write(), as write_lock is
        non-reentrant and doing so would deadlock. Reads via fetchall() are safe.
        """
        self._check_main_pid()
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

        with self.write_lock:
            conn = self._get_conn()
            result = conn.exec_driver_sql(sql, tuple(binds))
            if options['return_last_insert_rowid']:
                result = conn.execute(text('SELECT last_insert_rowid() as rowid')).scalar_one()

            self.middleware.call_hook_inline('datastore.post_execute_write', sql, binds, options)

        return result

    @private
    def fetchall(self, query, params=None):
        """Execute a query and return all rows as a list of mappings.

        Accepts either a raw SQL string or a SQLAlchemy selectable. Read operations
        do not acquire the write lock and are safe to call concurrently from multiple
        threads.
        """
        conn = self._get_conn()
        cursor = conn.execute(text(query) if isinstance(query, str) else query, params or {})
        try:
            return list(cursor.mappings())
        finally:
            cursor.close()
