"""
SQLite3 backend for django.

Works with either the pysqlite2 module or the sqlite3 module in the
standard library.
"""
from __future__ import unicode_literals

import logging
import os
import socket
import threading
import xmlrpclib

from django.db.backends.sqlite3 import base as sqlite3base
from lockfile import LockFile, LockTimeout
import cPickle as pickle
import sqlparse

Database = sqlite3base.Database
DatabaseError = sqlite3base.DatabaseError
IntegrityError = sqlite3base.IntegrityError

log = logging.getLogger('freeadmin.sqlite3_ha')


NO_SYNC_MAP = {
    'network_globalconfiguration': {
        'fields': ['gc_hostname'],
    },
    'system_systemdataset': {
        'fields': ['sys_uuid'],
    },
    'directoryservice_activedirectory': {
        'fields': ['ad_netbiosname'],
    },
    'system_failover': {
        'fields': ['ipaddress'],
    },
    'network_interfaces': {},
    'network_alias': {},
    'network_carp': {
        'fields': ['carp_skew'],
    },
}


class Journal(object):

    JOURNAL_FILE = '/data/ha-journal'

    def _get_queries(self):
        try:
            with open(self.JOURNAL_FILE, 'rb') as f:
                self.queries = pickle.loads(f.read())
        except (pickle.PickleError, EOFError):
            self.queries = []

    def __enter__(self):
        self._lock = LockFile(self.JOURNAL_FILE)
        while not self._lock.i_am_locking():
            try:
                self._lock.acquire(timeout=5)
            except LockTimeout:
                self._lock.break_lock()

        if not os.path.exists(self.JOURNAL_FILE):
            open(self.JOURNAL_FILE, 'a').close()

        self._get_queries()
        return self

    def __exit__(self, typ, value, traceback):

        with open(self.JOURNAL_FILE, 'w+') as f:
            if self.queries:
                f.write(pickle.dumps(self.queries))

        self._lock.release()
        if typ is not None:
            raise


class RunSQLRemote(threading.Thread):

    def __init__(self, *args, **kwargs):
        self._method = kwargs.pop('method', 'run_sql')
        self._sql = kwargs.pop('sql')
        self._params = kwargs.pop('params')
        super(RunSQLRemote, self).__init__(*args, **kwargs)

    def run(self):
        # FIXME: cache value
        from freenasUI.middleware.notifier import notifier
        s = xmlrpclib.ServerProxy('http://%s:8000' % (
            notifier().failover_peerip()
        ), allow_none=True)
        try:
            getattr(s, self._method)(self._sql, self._params)
        except socket.error as err:
            with Journal() as f:
                f.queries.append((self._sql, self._params))
        except Exception as err:
            log.error('Failed to run SQL remotely %s: %s', self._sql, err)


class DatabaseFeatures(sqlite3base.DatabaseFeatures):
    pass


class DatabaseOperations(sqlite3base.DatabaseOperations):
    pass


class DatabaseWrapper(sqlite3base.DatabaseWrapper):

    def create_cursor(self):
        return self.connection.cursor(factory=HASQLiteCursorWrapper)

    def dump_send(self):
        cur = self.cursor()
        cur.executelocal("select name from sqlite_master where type = 'table'")

        script = []
        for row in cur.fetchall():
            table = row[0]
            if table in NO_SYNC_MAP:
                tbloptions = NO_SYNC_MAP.get(table)
                if not tbloptions:
                    continue
            cur.executelocal("PRAGMA table_info('%s');" % table)
            fieldnames = [i[1] for i in cur.fetchall()]
            script.append('DELETE FROM %s' % table)
            cur.executelocal('SELECT %s FROM %s' % (
                "'INSERT INTO %s (%s) VALUES (' || %s ||')'" % (
                    table,
                    ', '.join(['`%s`' % f for f in fieldnames]),
                    " || ',' || ".join(
                        ['quote(`%s`)' % field for field in fieldnames]
                    ),
                ),
                table,
            ))
            for row in cur.fetchall():
                script.append(row[0])
        rsr = RunSQLRemote(method='sync_from', sql=script, params=None)
        rsr.run()

        return script

    def dump_recv(self, script):
        cur = self.cursor()
        cur.executelocal("select name from sqlite_master where type = 'table'")

        for row in cur.fetchall():
            table = row[0]
            if table not in NO_SYNC_MAP:
                continue
            tbloptions = NO_SYNC_MAP.get(table)
            if not tbloptions:
                cur.executelocal("PRAGMA table_info('%s');" % table)
                fieldnames = [i[1] for i in cur.fetchall()]
                script.append('DELETE FROM %s' % table)
                cur.executelocal('SELECT %s FROM %s' % (
                    "'INSERT INTO %s (%s) VALUES (' || %s ||')'" % (
                        table,
                        ', '.join(['`%s`' % f for f in fieldnames]),
                        " || ',' || ".join(
                            ['quote(`%s`)' % field for field in fieldnames]
                        ),
                    ),
                    table,
                ))
                for row in cur.fetchall():
                    script.append(row[0])
            else:
                fieldnames = tbloptions['fields']
                cur.executelocal('SELECT %s FROM %s' % (
                    "'UPDATE %s SET ' || %s || ' WHERE id = ' || id" % (
                        table,
                        " || ', ' || ".join([
                            "'`%s` = ' || quote(`%s`)" % (f, f)
                            for f in fieldnames
                        ]),
                    ),
                    table,
                ))
                for row in cur.fetchall():
                    script.append(row[0])
        cur.executescript(';'.join(
            ['PRAGMA foreign_keys=OFF', 'BEGIN TRANSACTION'] + script + [
                'COMMIT;'
            ]
        ))


class HASQLiteCursorWrapper(Database.Cursor):

    def execute_passive(self, query, params=None):

        try:
            # FIXME: This is extremely time-consuming
            from freenasUI.middleware.notifier import notifier
            if not (
                hasattr(notifier, 'failover_status') and
                notifier().failover_status() == 'MASTER'
            ):
                return
        except:
            return

        parse = sqlparse.parse(query)
        for p in parse:
            if p.tokens[0].normalized not in ('DELETE', 'INSERT', 'UPDATE'):
                continue

            cparams = list(params)
            if p.tokens[0].normalized == 'INSERT':

                into = p.token_next_match(0, sqlparse.tokens.Keyword, 'INTO')
                if not into:
                    continue

                next_ = p.token_next(into)

                if next_.get_name() in NO_SYNC_MAP:
                    continue

            elif p.tokens[0].normalized == 'DELETE':

                from_ = p.token_next_match(0, sqlparse.tokens.Keyword, 'FROM')
                if not from_:
                    continue

                next_ = p.token_next(from_)

                if next_.get_name() in NO_SYNC_MAP:
                    continue

            elif p.tokens[0].normalized == 'UPDATE':

                name = p.token_next(p.tokens[0]).get_name()
                no_sync = NO_SYNC_MAP.get(name)
                # Skip if table is in set to not to sync and has no attrs
                if no_sync is None and name in NO_SYNC_MAP:
                    continue

                set_ = p.token_next_match(0, sqlparse.tokens.Keyword, 'SET')
                if not set_:
                    continue

                next_ = p.token_next(set_)
                if not next_:
                    continue

                if no_sync is None:
                    lookup = []
                else:
                    if issubclass(next_.__class__, sqlparse.sql.IdentifierList):
                        lookup = list(next_.get_sublists())
                    elif issubclass(next_.__class__, sqlparse.sql.Comparison):
                        lookup = [next_]

                    # Get all placeholders from the query (%s)
                    placeholders = [a for a in p.flatten() if a.value == '%s']

                for l in lookup:

                    if l.get_name() not in no_sync['fields']:
                        continue

                    # Remove placeholder from the params
                    try:
                        idx = placeholders.index(l.tokens[-1])
                        if cparams:
                            del cparams[idx]
                    except ValueError:
                        pass

                    # If it is a list we must also remove the comma around it
                    prev_ = l.parent.token_prev(l)
                    next_ = l.parent.token_next(l)
                    if next_ and issubclass(
                        next_.__class__, sqlparse.sql.Token
                    ) and next_.value == ',':
                        del l.parent.tokens[l.parent.token_index(next_)]
                    elif prev_ and issubclass(
                        prev_.__class__, sqlparse.sql.Token
                    ) and prev_.value == ',':
                        del l.parent.tokens[l.parent.token_index(prev_)]
                    del l.parent.tokens[l.parent.token_index(l)]

            if params is not None:
                sql = self.convert_query(str(p))
            else:
                sql = str(p)
            rsr = RunSQLRemote(sql=sql, params=cparams)
            rsr.start()

    def execute(self, query, params=None):
        self.execute_passive(query, params=params)
        if params is None:
            return Database.Cursor.execute(self, query)
        query = self.convert_query(query)
        return Database.Cursor.execute(self, query, params)

    def executelocal(self, query, params=None):
        if params is None:
            return Database.Cursor.execute(self, query)
        query = self.convert_query(query)
        return Database.Cursor.execute(self, query, params)

    def executemany(self, query, param_list):
        query = self.convert_query(query)
        return Database.Cursor.executemany(self, query, param_list)

    def convert_query(self, query):
        return sqlite3base.FORMAT_QMARK_REGEX.sub('?', query).replace(
            '%%', '%'
        )
