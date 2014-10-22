__author__ = 'jceel'

import logging
import json
import psycopg2
import psycopg2.extras

class PostgresSelectQuery(object):
    ASC = 'ASC'
    DESC = 'DESC'

    def __init__(self, table, cur):
        self.cur = cur
        self.table = table
        self.connect = 'AND'
        self.where_conditions = []
        self.sort_field = None
        self.sort_dir = PostgresSelectQuery.DESC
        self.limit_value = None

    def __convert_path(self, path):
        return '(data->' + '->'.join(["'" + i + "'" for i in path.split('.')]) + ')::text'

    def __build_where(self):
        items = []
        for left, op, right in self.where_conditions:
            path = left if left == 'id' else self.__convert_path(left)
            items.append(self.cur.mogrify("{0} {1} %s".format(path, op), (json.dumps(right),)))

        return self.connect.join(items)

    def projection(self, projection):
        pass

    def where(self, left, op, right):
        self.where_conditions.append((left, op, right))

    def sort(self, field, dir):
        self.sort_field = self.__convert_path(field)
        self.sort_dir = dir

    def limit(self, limit):
        self.limit_value = limit

    def sql(self):
        result = ['SELECT id, data FROM {0}'.format(self.table)]
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

    def collection_create(self, collection, pkey_type='uuid'):
        with self.conn.cursor() as cur:
            cur.execute("CREATE TABLE {0} (id {1} PRIMARY KEY, data json)".format(collection, pkey_type))

        self.conn.commit()

    def collection_exists(self, collection):
        with self.conn.cursor() as cur:
            cur.execute("SELECT exists(SELECT * FROM information_schema.tables WHERE table_name = %s)", (collection,))
            return cur.fetchone()[0]

    def collection_list(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", ('public',))
            for i in cur:
                yield i[0]

    def query(self, collection, args=[], sort=None, dir=None, limit=None):
        with self.conn.cursor() as cur:
            query = PostgresSelectQuery(collection, cur)
            for i in args:
                query.where(*i)

            if sort and dir:
                query.sort(sort, dir)

            if limit:
                query.limit(limit)

            cur.execute(query.sql())

            for i in cur:
                row = i.data
                row["id"] = i.id
                yield row

    def get_count(self, collection, args=[]):
        pass

    def get_one(self, collection, args=[]):
        with self.conn.cursor() as cur:
            query = PostgresSelectQuery(collection, cur)
            for i in args:
                query.where(*i)

            query.limit(1)
            cur.execute(query.sql())

            i = cur.fetchone()
            row = i.data
            row["id"] = i.id
            return row

    def get_by_id(self, collection, pkey):
        return self.get_one(collection, [('id', '=', pkey)])

    def insert(self, collection, obj, pkey=None):
        if hasattr(obj, '__getstate__'):
            obj = obj.__getstate__()

        with self.conn.cursor() as cur:
            pkey = 'default' if pkey is None else cur.mogrify('%s', pkey)
            cur.execute("INSERT INTO {0} (id, data) VALUES ({1}, %s) RETURNING id".format(
                collection,
                pkey
            ), (psycopg2.extras.Json(obj),))

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

    def upsert(self, collection, pkey, obj):
        if self.exists(collection, [('id', '=', pkey)]):
            return self.update(collection, pkey, obj)
        else
            return self.insert(collection, pkey, obj)

    def exists(self, collection, args=[]):
        return self.get_one(collection, args) is not None