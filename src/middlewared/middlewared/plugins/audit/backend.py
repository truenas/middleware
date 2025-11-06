import csv
import errno
import json
import os
import subprocess
import threading
import time
import yaml

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
from middlewared.service import job, periodic, Service
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.itertools import batched

from middlewared.plugins.audit.utils import AUDITED_SERVICES, audit_file_path, AUDIT_TABLES, AUDIT_CHUNK_SZ
from middlewared.plugins.datastore.filter import FilterMixin
from middlewared.plugins.datastore.schema import SchemaMixin
from middlewared.utils.jsonpath import json_path_parse, JSON_PATH_PREFIX
from truenas_api_client import ejson


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

    def batched_entries(self, cursor, select):
        """ convert rows into lists of dictionaries based on our chunk size """
        for rows in batched(cursor, AUDIT_CHUNK_SZ):
            output = []
            for row in rows:
                entry = {}
                if not select:
                    for column in self.table.c:
                        column_name = str(column.name)
                        entry[column_name] = getattr(row, column_name)

                else:
                    for column_name in select:
                        if isinstance(column_name, list):
                            # handling SELECT ... AS results data can be regular string, NULL, int, or even JSON
                            column_name = column_name[1]
                            if (data := getattr(row, column_name)) is None:
                                entry[column_name] = None
                            elif isinstance(data, str):
                                # Majority of time these will probably be JSON objects extracted
                                # via json_extract()
                                try:
                                    entry[column_name] = ejson.loads(data)
                                except json.decoder.JSONDecodeError:
                                    entry[column_name] = data
                            else:
                                entry[column_name] = data
                        else:
                            entry[column_name] = getattr(row, column_name)

                output.append(entry)

            yield output

    def fetchall(self, query, select, is_count):
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
                cursor = self.connection.execute(query, [])
            except DBAPIError as e:
                # We want to squash errors that are due to presence of missing
                # table. See note for audit_table_exists() method.
                if not str(e.orig).startswith('no such table'):
                    raise

                yield 0 if is_count else []
                return

            try:
                if is_count:
                    results = cursor.fetchall()
                    if not results:
                        yield 0
                    yield results[0]['count']
                for batch in self.batched_entries(cursor, select):
                    yield batch
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

    def __fetchall(self, conn, qs, filters, options, retry=True):
        """
        This is a wrapper for retrieving db contents based on the specified sqlalchemy queryset. It is
        consumed ultimately by audit.query. I'm currently passing `filters` here but not using
        in case we need to implement python-based filtering on smaller chunk sizes.
        The primary case where we'd want python-based filtering is if we need to allow filtering
        based on fields within the event_data or svc_data. For example "event_data.proctitle".

        The chunk size for audit queries should match precisely with the maximum limit allowed
        by our query-options validation, and so in theory this should only ever do one iteration
        but we can tune down the AUDIT_CHUNK_SZ if we find out that 10K entries is too large to
        manage at once.
        """
        data = []

        try:
            for batch in conn.fetchall(qs, options.get('select', []), options.get('count', False)):
                if isinstance(batch, int):
                    # we got the count rather than entries list
                    return batch

                # This should only happen once. PyList_Extend() will realloc the intial list
                # size and create new references to items for batch. So O(N), but really fast.
                # Memory cost is relatively small compared to everything else going on when
                # we're doing these operations.
                data.extend(batch)
        except RuntimeError:
            self.logger.critical('Failed to fetch information from audit database', exc_info=True)
            conn.setup()
            return self.__fetchall(conn, qs, filters, options, retry=False)

        return data

    def __get_audit_column(self, table, name, label):
        """ Get a column and apply a label to it if required """
        if name.startswith(JSON_PATH_PREFIX):
            name, path = json_path_parse(name)
            raw_column = self._get_col(table, name)
            if label:
                column = func.json_extract(raw_column, path).label(label)
            else:
                column = func.json_extract(raw_column, path)
        else:
            if label:
                column = self._get_col(table, name).label(label)
            else:
                column = self._get_col(table, name)

        return column

    def __create_select_columns(self, table, select):
        out = {}
        for i in select:
            if isinstance(i, list):
                entry = self.__get_audit_column(table, i[0], i[1])
                name = i[1]
            else:
                entry = self.__get_audit_column(table, i, None)
                name = i

            out[name] = entry

        return out

    def __create_queryset_common(self, conn, filters, options):
        """ common method between query and export to generate a queryset """
        order_by = options.get('order_by', []).copy()
        do_count = options.get('count', False)
        from_ = conn.table
        order_by_source = {col.name: col for col in conn.table.c}

        if do_count:
            qs = select(func.count('ROW_ID').label('count')).select_from(from_)
        else:
            to_select = options.get('select', [])
            if not to_select:
                # We treat absence of explicit select as ALL
                columns = list(conn.table.c)
            else:
                target_dict = self.__create_select_columns(conn.table, to_select)
                columns = list(target_dict.values())
                # We may have created additional fields via SELECT AS
                order_by_source |= target_dict

            qs = select(*columns).select_from(from_)

        if filters:
            qs = qs.where(and_(*self._filters_to_queryset(filters, conn.table, None, {})))

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
                    order_by[i] = order_by_source[order[1:]].desc()
                else:
                    order_by[i] = order_by_source[order]

                if wrapper is not None:
                    order_by[i] = wrapper(order_by[i])

            qs = qs.order_by(*order_by)

        if options['offset']:
            qs = qs.offset(options['offset'])

        if options['limit']:
            qs = qs.limit(options['limit'])

        return qs

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

        # we need a sanity check here to avoid loading huge audit tables into memory
        if not options['count'] and not options['limit']:
            raise CallError(
                'Auditing queries require pagination of results. This means that '
                'you can either retrieve the row count, or specify a limit on number of '
                'results.', errno.E2BIG
            )

        qs = self.__create_queryset_common(conn, filters, options)

        result = self.__fetchall(conn, qs, filters, options)

        if options['get']:
            try:
                return result[0]
            except IndexError:
                raise MatchNotFound() from None

        return result

    @job()
    def export_to_file(self, job, db_name, export_format, destination, filters, options):
        job.set_progress(None, f'Quering data for {export_format} audit report')

        if options.get('count'):
            raise CallError('Exporting count to file is not supported')

        try:
            conn = self.connections[db_name]
        except KeyError:
            raise CallError(f'Invalid database name: {db_name!r}')

        if conn.connection is None:
            raise CallError(f'{db_name}: connection to audit database is not initialized.')

        qs = self.__create_queryset_common(conn, filters, options)

        # Write our audit table entries to separate files on disk based on the specified
        # format in AUDIT_CHUNK_SZ batches. Once this is complete we will create a tar.gz
        # file for them by using `tar -cz` command to avoid having extra copies of buffers
        # in the middlewared process during python tarfile operations.
        dest_tar = f'{destination}.tar.gz'
        for idx, batch in enumerate(conn.fetchall(
            qs, options.get('select', []), options.get('count', False)
        )):
            member_name = os.path.basename(destination.replace(
                export_format.lower(), f'part_{idx:05d}.{export_format.lower()}'
            ))
            job.set_progress(50, f'Writing report component: {member_name}')
            with open(os.path.join(destination, member_name), 'w') as f:
                match export_format:
                    case 'JSON':
                        ejson.dump(batch, f, indent=4)
                    case 'CSV':
                        fieldnames = batch[0].keys()
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()

                        for entry in batch:
                            for key in fieldnames:
                                if isinstance(entry[key], dict):
                                    entry[key] = ejson.dumps(entry[key])

                            writer.writerow(entry)
                    case 'YAML':
                        yaml.dump(batch, f)
                    case _:
                        raise ValueError(f'{export_format}: unexpected export format')

                f.flush()

        job.set_progress(75, 'Compressing report')
        subprocess.run(['tar', '-cvzf', dest_tar, destination, '--remove-files'])
        job.set_progress(100, f'Audit report completed and available at {dest_tar}')
        return dest_tar

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
