#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import logging
import json
import psycopg2
import psycopg2.extras
from datastore import DuplicateKeyException

class PostgresSelectQuery(object):
    ASC = 'ASC'
    DESC = 'DESC'

    def __init__(self, table, cur):
        self.cur = cur
        self.table = table
        self.connect = 'AND'
        self.where_conditions = []
        self.projection_func = None
        self.sort_field = None
        self.sort_dir = PostgresSelectQuery.DESC
        self.limit_value = None

    def __convert_path(self, path):
        return '(data->' + '->'.join(["'" + i + "'" for i in path.split('.')]) + ')::text'

    def __build_where(self):
        items = []
        for left, op, right in self.where_conditions:
            if left == 'id':
                path = left
                items.append(self.cur.mogrify("{0} {1} %s".format(path, op), (right,)))
            else:
                path = self.__convert_path(left)
                items.append(self.cur.mogrify("{0} {1} %s".format(path, op), (psycopg2.extras.Json(right),)))

        return self.connect.join(items)

    def projection(self, projection):
        self.projection_func = projection

    def where(self, left, op, right):
        self.where_conditions.append((left, op, right))

    def sort(self, field, dir):
        self.sort_field = self.__convert_path(field)
        self.sort_dir = dir

    def limit(self, limit):
        self.limit_value = limit

    def sql(self):
        result = []

        if self.projection_func:
            result.append('SELECT {0}(id, data) FROM {1}'.format(self.projection_func, self.table))
        else:
            result.append('SELECT id, data FROM {0}'.format(self.table))

        if self.where_conditions:
            result.append('WHERE {0}'.format(self.__build_where()))

        if self.sort_field:
            result.append('ORDER BY {0} {1}'.format(self.sort_field, self.sort_dir))

        if self.limit_value:
            result.append('LIMIT {0}'.format(self.limit_value))

        return ' '.join(result)


class PostgresDatastore(object):
    def __init__(self):
        self.logger = logging.getLogger('PostgresDatastore')

    def __get_column_datatype(self, table):
        with self.conn.cursor() as cur:
            cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name = %s", (table))
            return cur.fetchone()[0]

    def connect(self, dsn):
        self.conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.NamedTupleCursor)
        psycopg2.extras.register_uuid(self.conn)

    def collection_create(self, collection, pkey_type='uuid', attributes={}):
        with self.conn.cursor() as cur:
            cur.execute("CREATE TABLE {0} (id {1} PRIMARY KEY, data json)".format(collection, pkey_type))
            self.insert('__collections', attributes, pkey=collection)

        self.conn.commit()

    def collection_get_pkey_type(self, collection):
        with self.conn.cursor() as cur:
            cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name = %s AND column_name = 'id'", [collection])
            return cur.fetchone()[0]

    def collection_get_max_id(self, collection):
        with self.conn.cursor() as cur:
            cur.execute("SELECT max(id) FROM {0}".format(collection))
            return cur.fetchone()[0]

    def collection_get_attrs(self, collection):
        return self.get_by_id('__collections', collection)

    def collection_set_attrs(self, collection, attributes):
        self.update('__collections', collection, attributes)

    def collection_exists(self, collection):
        with self.conn.cursor() as cur:
            cur.execute("SELECT exists(SELECT * FROM information_schema.tables WHERE table_name = %s)", (collection,))
            return cur.fetchone()[0]

    def collection_delete(self, collection):
        with self.conn.cursor() as cur:
            cur.execute("DROP TABLE {0}".format(collection))

        self.conn.commit()

    def collection_list(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", ('public',))
            for i in cur:
                if i[0].startswith('__'):
                    continue

                yield i[0]

    def query(self, collection, *args, **kwargs):
        wrap = kwargs.pop('wrap', True)
        with self.conn.cursor() as cur:
            query = PostgresSelectQuery(collection, cur)
            for i in args:
                query.where(*i)

            if 'sort' in kwargs and 'dir' in kwargs:
                query.sort(kwargs.pop('sort'), kwargs.pop('dir'))

            if 'limit' in kwargs:
                query.limit(kwargs.pop('limit'))

            cur.execute(query.sql())

            for i in cur:
                if not wrap:
                    yield i
                    continue

                row = i.data
                row["id"] = i.id
                yield row

    def get_count(self, collection, *args):
         with self.conn.cursor() as cur:
            query = PostgresSelectQuery(collection, cur)
            for i in args:
                query.where(*i)

            query.projection('count')
            cur.execute(query.sql())

            i = cur.fetchone()
            return i[0]

    def get_one(self, collection, *args, **kwargs):
        wrap = kwargs.pop('wrap', True)
        with self.conn.cursor() as cur:
            query = PostgresSelectQuery(collection, cur)
            for i in args:
                query.where(*i)

            query.limit(1)
            cur.execute(query.sql())

            i = cur.fetchone()
            if i is None:
                return None

            if not wrap:
                return i

            row = i.data
            row["id"] = i.id
            return row

    def get_by_id(self, collection, pkey):
        return self.get_one(collection, [('id', '=', pkey)])

    def insert(self, collection, obj, pkey=None):
        if hasattr(obj, '__getstate__'):
            obj = obj.__getstate__()

        if type(obj) is dict and 'id' in obj:
            pkey = obj.pop('id')

        with self.conn.cursor() as cur:
            pkey = 'default' if pkey is None else cur.mogrify('%s', [pkey])
            try:
                cur.execute("INSERT INTO {0} (id, data) VALUES ({1}, %s) RETURNING id".format(
                    collection,
                    pkey
                ), (psycopg2.extras.Json(obj),))
            except psycopg2.IntegrityError, e:
                self.conn.rollback()
                raise DuplicateKeyException(e)
            else:
                self.conn.commit()

            result = cur.fetchone()
            self.conn.commit()
            return result[0]

    def update(self, collection, pkey, obj):
        if hasattr(obj, '__getstate__'):
            obj = obj.__getstate__()

        with self.conn.cursor() as cur:
            cur.execute("UPDATE {0} SET data = %s WHERE id = %s".format(collection), (
                psycopg2.extras.Json(obj),
                pkey
            ))

            self.conn.commit()

    def upsert(self, collection, pkey, obj):
        if self.exists(collection, [('id', '=', pkey)]):
            return self.update(collection, pkey, obj)
        else:
            return self.insert(collection, obj, pkey)

    def delete(self, collection, pkey):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM {0} WHERE id = %s".format(collection), (
                pkey
            ))

            self.conn.commit()

    def exists(self, collection, *args):
        return self.get_one(collection, *args) is not None