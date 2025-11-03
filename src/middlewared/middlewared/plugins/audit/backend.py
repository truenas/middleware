import errno
import os
import threading
import time

from pydantic import Field
from sqlalchemy import create_engine, inspect
from sqlalchemy import and_, func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import nullsfirst, nullslast

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.base.types import NonEmptyString
from middlewared.api.current import GenericQueryResult, QueryFilters, QueryOptions
from middlewared.service import periodic, Service
from middlewared.service_exception import CallError, MatchNotFound

from middlewared.plugins.audit.utils import AUDITED_SERVICES, audit_file_path, AUDIT_TABLES
from middlewared.plugins.datastore.filter import FilterMixin
from middlewared.plugins.datastore.schema import SchemaMixin


class AuditBackendQueryArgs(BaseModel):
    db_name: NonEmptyString
    query_filters: QueryFilters = []
    query_options: QueryOptions = Field(default_factory=QueryOptions)


class AuditBackendQueryResult(GenericQueryResult):
    pass


class SQLConn:
    def __init__(self, svc, vers):
        svcs = [svc[0] for svc in AUDITED_SERVICES]
        if svc not in svcs:
            raise ValueError(f'{svc}: unknown service')

        self.table = AUDIT_TABLES[svc]
        self.table_name = f'audit_{svc}_{str(vers).replace(".", "_")}'
        self.path = audit_file_path(svc)
        self.engine = None
        self.connection = None
        self.lock = threading.RLock()
        self.dbfd = -1

    def audit_table_exists(self):
        """
        syslog-ng creates the audit table on first message insertion, and
        so it's reasonable to expect a freshly installed or upgraded system
        to have empty sqlite3 databases.
        """
        with self.lock:
            return inspect(self.engine).has_table(self.table_name)

    def setup(self):
        with self.lock:
            if self.engine is not None:
                self.engine.dispose()

            if self.connection is not None:
                self.connection.close()

            if self.dbfd != -1:
                os.close(self.dbfd)
                self.dbfd = -1

            self.engine = create_engine(
                f'sqlite:///{self.path}',
                connect_args={'check_same_thread': False}
            )
            self.connection = self.engine.connect()
            self.connection.execute('PRAGMA journal_mode=WAL')
            self.dbfd = os.open(self.path, os.O_PATH)

    def fetchall(self, query, params=None):
        with self.lock:
            if (st := os.fstat(self.dbfd)).st_nlink == 0:
                raise RuntimeError(
                    f'{self.path}: audit database was unexpectedly deleted.'
                )

            try:
                if os.lstat(self.path).st_ino != st.st_ino:
                    raise RuntimeError(
                        f'{self.path}: audit database was unexpectedly replaced.'
                    )
            except FileNotFoundError:
                raise RuntimeError(f'{self.path}: audit database was renamed.')

            try:
                cursor = self.connection.execute(query, params or [])
            except DBAPIError as e:
                # We want to squash errors that are due to presence of missing
                # table. See note for audit_table_exists() method.
                if not str(e.orig).startswith('no such table'):
                    raise

                return []

            try:
                return cursor.fetchall()
            finally:
                cursor.close()

    def enforce_retention(self, days):
        if not days or days < 0:
            raise ValueError("Days must be positive value greater than zero.")

        if not self.audit_table_exists():
            return

        secs = days * 86400
        cutoff_ts = int(time.time()) - secs
        with self.lock:
            with Session(self.engine) as s:
                expired = s.query(self.table).filter(self.table.c.message_timestamp < cutoff_ts)
                expired.delete(synchronize_session=False)
                s.commit()

            self.connection.connection.execute('VACUUM')


class AuditBackendService(Service, FilterMixin, SchemaMixin):

    class Config:
        private = True

    connections = {svc[0]: SQLConn(*svc) for svc in AUDITED_SERVICES}

    def setup(self):
        """
        This method reinitializes the database connections for audit databases.

        Examples of when this is necessary are:
        - initial middlewared startup
        - after audit database deletion or rename
        """
        for svc, conn in self.connections.items():
            # Dismiss any existing AuditSetup one-shot alerts
            self.middleware.call_sync('alert.oneshot_delete', 'AuditBackendSetup', {"service": svc})
            try:
                conn.setup()
            except Exception:
                self.middleware.call_sync('alert.oneshot_create', 'AuditBackendSetup', {"service": svc})
                self.logger.error(
                    '%s: failed to set up auditing database connection.',
                    svc, exc_info=True
                )

    def serialize_results(self, results, table, select):
        out = []
        for row in results:
            entry = {}
            for column in table.c:
                column_name = str(column.name)
                if select and column_name not in select:
                    continue

                entry[column_name] = row[column]

            out.append(entry)

        return out

    def __fetchall(self, conn, qs):
        try:
            data = conn.fetchall(qs)
        except RuntimeError:
            self.logger.critical('Failed to fetch information from audit database', exc_info=True)
            conn.setup()
            data = conn.fetchall(qs)

        return data

    @api_method(AuditBackendQueryArgs, AuditBackendQueryResult, private=True)
    def query(self, db_name, filters, options):
        """
        Query the specied auditable service's database based on the specified
        `query-filters` and `query-options`. This is the private endpoint for the
        audit backend and so it should generally not be used by websocket API
        consumers except in special circumstances.
        """
        try:
            conn = self.connections[db_name]
        except KeyError:
            raise CallError(f'Invalid database name: {db_name!r}')

        if conn.connection is None:
            raise CallError(f'{db_name}: connection to audit database is not initialized.')

        order_by = options.get('order_by', []).copy()
        from_ = conn.table

        if not options['count'] and not options['limit']:
            raise CallError(
                'Auditing queries require pagination of results. This means that '
                'you can either retrieve the row count, or specify a limit on number of '
                'results.', errno.E2BIG
            )

        if options['count']:
            qs = select([func.count('ROW_ID')]).select_from(from_)
        else:
            columns = list(conn.table.c)
            qs = select(columns).select_from(from_)

        if filters:
            qs = qs.where(and_(*self._filters_to_queryset(filters, conn.table, None, {})))

        if options['count']:
            if not (results := self.__fetchall(conn, qs)):
                return 0

            return results[0][0]

        if order_by:
            for i, order in enumerate(order_by):
                wrapper = None
                if order.startswith('nulls_first:'):
                    wrapper = nullsfirst
                    order = order[len('nulls_first:'):]
                elif order.startswith('nulls_last:'):
                    wrapper = nullslast
                    order = order[len('nulls_last:'):]

                if order.startswith('-'):
                    order_by[i] = self._get_col(conn.table, order[1:], None).desc()
                else:
                    order_by[i] = self._get_col(conn.table, order, None)

                if wrapper is not None:
                    order_by[i] = wrapper(order_by[i])

            qs = qs.order_by(*order_by)

        if options['offset']:
            qs = qs.offset(options['offset'])

        if options['limit']:
            qs = qs.limit(options['limit'])

        result = self.__fetchall(conn, qs)

        if options['get']:
            try:
                return result[0]
            except IndexError:
                raise MatchNotFound() from None

        return self.serialize_results(result, conn.table, options.get('select'))

    @periodic(interval=86400, run_on_start=False)
    def __lifecycle_cleanup(self):
        """
        This is a private method that should only be called as a periodic task.
        It deletes database entries that are older than the specified lifetime.
        """
        retention_period = self.middleware.call_sync('datastore.config', 'system.audit')['retention']
        for svc, conn in self.connections.items():
            try:
                conn.enforce_retention(retention_period)
            except Exception:
                self.logger.error(
                    "%s: failed to enforce retention on audit DB.",
                    svc, exc_info=True
                )
        try:
            self.middleware.call_sync('audit.cleanup_reports')
        except Exception:
            self.logger.warning(
                'Cleanup of auditing report directory failed',
                exc_info=True
            )
