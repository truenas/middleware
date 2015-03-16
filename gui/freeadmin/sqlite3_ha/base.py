"""
SQLite3 backend for django.

Works with either the pysqlite2 module or the sqlite3 module in the
standard library.
"""
from __future__ import unicode_literals

import logging
import threading
import xmlrpclib

from django.db.backends.sqlite3 import base as sqlite3base
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


class RunSQLRemote(threading.Thread):

    def __init__(self, *args, **kwargs):
        self._sql = kwargs.pop('sql')
        self._params = kwargs.pop('params')
        super(RunSQLRemote, self).__init__(*args, **kwargs)

    def run(self):
        # FIXME: cache value
        from freenasUI.middleware.notifier import notifier
        s = xmlrpclib.ServerProxy('http://%s:8000' % (
            notifier().failover_peerip()
        ))
        try:
            s.run_sql(self._sql, self._params)
        except Exception as err:
            log.error('Failed to run SQL remotely %s: %s', self._sql, err)



class DatabaseFeatures(sqlite3base.DatabaseFeatures):
    pass


class DatabaseOperations(sqlite3base.DatabaseOperations):
    pass


class DatabaseWrapper(sqlite3base.DatabaseWrapper):

    def create_cursor(self):
        return self.connection.cursor(factory=HASQLiteCursorWrapper)


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

    def executemany(self, query, param_list):
        query = self.convert_query(query)
        return Database.Cursor.executemany(self, query, param_list)

    def convert_query(self, query):
        return sqlite3base.FORMAT_QMARK_REGEX.sub('?', query).replace(
            '%%', '%'
        )
