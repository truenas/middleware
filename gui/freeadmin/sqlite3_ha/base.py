"""
SQLite3 backend for django.

Works with either the pysqlite2 module or the sqlite3 module in the
standard library.
"""
from __future__ import unicode_literals

import logging

from django.db.backends.sqlite3 import base as sqlite3base
import sqlparse

Database = sqlite3base.Database
DatabaseError = sqlite3base.DatabaseError
IntegrityError = sqlite3base.IntegrityError

log = logging.getLogger('freeadmin.sqlite3_ha')


class DatabaseFeatures(sqlite3base.DatabaseFeatures):
    pass


class DatabaseOperations(sqlite3base.DatabaseOperations):
    pass


class DatabaseWrapper(sqlite3base.DatabaseWrapper):

    def create_cursor(self):
        return self.connection.cursor(factory=HASQLiteCursorWrapper)


class HASQLiteCursorWrapper(Database.Cursor):

    def execute(self, query, params=None):
        parse = sqlparse.parse(query)
        for p in parse:
            if p.tokens[0].normalized not in ('DELETE', 'INSERT', 'UPDATE'):
                continue

            if p.tokens[0].normalized == 'UPDATE':

                name = p.token_next(p.tokens[0]).get_name()
                if name not in (
                    'network_globalconfiguration',
                ):
                    continue

                set_ = p.token_next_match(0, sqlparse.tokens.Keyword, 'SET')
                if not set_:
                    continue

                next_ = p.token_next(set_)
                if not next_:
                    continue

                if issubclass(next_.__class__, sqlparse.sql.IdentifierList):
                    lookup = list(next_.get_sublists())
                elif issubclass(next_.__class__, sqlparse.sql.Comparison):
                    lookup = [next_]

                for l in lookup:

                    if l.get_name() not in ('gc_hosts'):
                        continue

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
