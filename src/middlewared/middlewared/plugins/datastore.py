from concurrent.futures import ThreadPoolExecutor
import operator

from sqlalchemy import and_, create_engine, func, select
from sqlalchemy.sql import Alias

from middlewared.schema import accepts, Any, Bool, Dict, Int, List, Ref, Str
from middlewared.service import CallError, private, Service
from middlewared.sqlalchemy import Model
from middlewared.service_exception import MatchNotFound

from middlewared.plugins.config import FREENAS_DATABASE


class DatastoreService(Service):

    class Config:
        private = True

    thread_pool = None
    connection = None

    @private
    async def setup(self):
        self.thread_pool = ThreadPoolExecutor(1)
        self.connection = await self.middleware.run_in_executor(
            self.thread_pool,
            lambda: create_engine(f'sqlite:///{FREENAS_DATABASE}').connect()
        )

    @private
    def fetchall(self, query, params=None):
        cursor = self.connection.execute(query, params or [])
        try:
            return cursor.fetchall()
        finally:
            cursor.close()

    def _get_table(self, name):
        return Model.metadata.tables[name.replace('.', '_')]

    def _get_col(self, table, name, prefix=None):
        # id is special
        if name != 'id' and prefix:
            name = prefix + name

        if name not in table.c and f'{name}_id' in table.c:
            name = f'{name}_id'

        return table.c[name]

    def _filters_to_queryset(self, filters, table, prefix=None):
        opmap = {
            '=': operator.eq,
            '!=': operator.ne,
            '>': operator.gt,
            '>=': operator.ge,
            '<': operator.lt,
            '<=': operator.le,
            '~': lambda col, value: col.op('regexp')(value),
            'in': operator.contains,
            'nin': lambda col, value: value not in col,
            '^': lambda col, value: col.startswith(value),
            '$': lambda col, value: col.endswith(value),
        }

        rv = []
        for f in filters:
            if not isinstance(f, (list, tuple)):
                raise ValueError('Filter must be a list or tuple: {0}'.format(f))
            if len(f) == 3:
                name, op, value = f
                if op not in opmap:
                    raise ValueError('Invalid operation: {0}'.format(op))
                q = opmap[op](self._get_col(table, name, prefix), value)
                rv.append(q)
            elif len(f) == 2:
                op, value = f
                if op == 'OR':
                    or_value = None
                    for value in self._filters_to_queryset(value, table, prefix):
                        if or_value is None:
                            or_value = value
                        else:
                            or_value |= value
                    rv.append(or_value)
                else:
                    raise ValueError('Invalid operation: {0}'.format(op))
            else:
                raise ValueError('Invalid filter {0}'.format(f))
        return rv

    def _get_queryset_joins(self, table):
        result = {}
        for column in table.c:
            if column.foreign_keys:
                if len(column.foreign_keys) > 1:
                    raise RuntimeError('Multiple foreign keys are not supported')

                foreign_key = list(column.foreign_keys)[0]
                alias = foreign_key.column.table.alias(foreign_key.name)

                result[foreign_key] = alias
                if foreign_key.column.table != (table.original if isinstance(table, Alias) else table):
                    result.update(self._get_queryset_joins(alias))

        return result

    async def _queryset_serialize(self, qs, table, aliases, extend, extend_context, field_prefix, select):
        if extend_context:
            extend_context_value = await self.middleware.call(extend_context)
        else:
            extend_context_value = None

        result = []
        for i in qs:
            result.append(await self._serialize(
                i, table, aliases,
                extend, extend_context, extend_context_value, field_prefix, select
            ))

        return result

    async def _serialize(self, obj, table, aliases, extend, extend_context, extend_context_value, field_prefix, select):
        data = self._serialize_row(obj, table, aliases, select)

        data = {k[len(field_prefix):] if field_prefix and k.startswith(field_prefix) else k: v
                for k, v in data.items()}

        if extend:
            if extend_context:
                data = await self.middleware.call(extend, data, extend_context_value)
            else:
                data = await self.middleware.call(extend, data)

        return data

    def _serialize_row(self, obj, table, aliases, select):
        data = {}

        for column in table.c:
            if select and column.name not in select:
                continue

            if not column.foreign_keys:
                data[column.name] = obj[column]

        for foreign_key, alias in aliases.items():
            column = foreign_key.parent

            if column.table != table:
                continue

            if not column.name.endswith('_id'):
                raise RuntimeError('Foreign key column must end with _id')

            data[column.name[:-3]] = (
                self._serialize_row(obj, alias, aliases, select) if obj[column] is not None else None
            )

        return data

    @accepts(
        Str('name'),
        List('query-filters', default=None, null=True, register=True),
        Dict(
            'query-options',
            Str('extend', default=None, null=True),
            Str('extend_context', default=None, null=True),
            Str('prefix', default=None, null=True),
            List('order_by', default=[]),
            List('select', default=[]),
            Bool('count', default=False),
            Bool('get', default=False),
            Int('limit', default=0),
            null=True,
            register=True,
        ),
    )
    async def query(self, name, filters=None, options=None):
        """
        Query for items in a given collection `name`.

        `filters` is a list which each entry can be in one of the following formats:

            entry: simple_filter | conjuntion
            simple_filter: '[' attribute_name, OPERATOR, value ']'
            conjunction: '[' CONJUNTION, '[' simple_filter (',' simple_filter)* ']]'

            OPERATOR: ('=' | '!=' | '>' | '>=' | '<' | '<=' | '~' | 'in' | 'nin')
            CONJUNCTION: 'OR'

        e.g.

        `['OR', [ ['username', '=', 'root' ], ['uid', '=', 0] ] ]`

        `[ ['username', '=', 'root' ] ]`

        .. examples(websocket)::

          Querying for username "root" and returning a single item:

            :::javascript
            {
              "id": "d51da71b-bb48-4b8b-a8f7-6046fcc892b4",
              "msg": "method",
              "method": "datastore.query",
              "params": ["account.bsdusers", [ ["username", "=", "root" ] ], {"get": true}]
            }
        """
        table = self._get_table(name)
        if options is None:
            options = {}
        else:
            # We do not want to make changes to original options
            # which might happen with "prefix"
            options = options.copy()

        aliases = None
        if options['count']:
            qs = select([func.count(table.c.id)])
        else:
            columns = list(table.c)
            from_ = table
            aliases = self._get_queryset_joins(table)
            for foreign_key, alias in aliases.items():
                columns.extend(list(alias.c))
                from_ = from_.outerjoin(alias, alias.c[foreign_key.column.name] == foreign_key.parent)

            qs = select(columns).select_from(from_)

        prefix = options['prefix']

        if filters:
            qs = qs.where(and_(*self._filters_to_queryset(filters, table, prefix)))

        if options['count']:
            return (await self.middleware.run_in_executor(self.thread_pool, self.fetchall, qs))[0][0]

        order_by = options['order_by']
        if order_by:
            # Do not change original order_by
            order_by = order_by[:]
            for i, order in enumerate(order_by):
                if order.startswith('-'):
                    order_by[i] = self._get_col(table, order[1:], prefix).desc()
                else:
                    order_by[i] = self._get_col(table, order, prefix)
            qs = qs.order_by(*order_by)

        if options['limit']:
            qs = qs.limit(options['limit'])

        result = []
        for i in await self._queryset_serialize(
            await self.middleware.run_in_executor(self.thread_pool, self.fetchall, qs),
            table, aliases, options['extend'], options['extend_context'], options['prefix'], options['select'],
        ):
            result.append(i)

        if options['get']:
            try:
                return result[0]
            except IndexError:
                raise MatchNotFound()

        return result

    @accepts(Str('name'), Ref('query-options'))
    async def config(self, name, options=None):
        """
        Get configuration settings object for a given `name`.

        This is a shortcut for `query(name, {"get": true})`.
        """
        options['get'] = True
        return await self.query(name, None, options)

    @accepts(Str('name'), Dict('data', additional_attrs=True), Dict('options', Str('prefix', default='')))
    async def insert(self, name, data, options=None):
        """
        Insert a new entry to `name`.
        """
        table = self._get_table(name)
        data = data.copy()

        for column in table.c:
            if column.foreign_keys:
                if column.name[:-3] in data:
                    data[column.name] = data[column.name[:-3]]

        insert = table.insert().values(**{options['prefix'] + k: v for k, v in data.items()})
        result = await self.middleware.run_in_executor(self.thread_pool, self.connection.execute, insert)
        return result.inserted_primary_key[0]

    @accepts(Str('name'), Any('id'), Dict('data', additional_attrs=True), Dict('options', Str('prefix', default='')))
    async def update(self, name, id, data, options=None):
        """
        Update an entry `id` in `name`.
        """
        table = self._get_table(name)
        data = data.copy()

        for column in table.c:
            if column.foreign_keys:
                if column.name[:-3] in data:
                    data[column.name] = data[column.name[:-3]]

        update = table.update().values(**{options['prefix'] + k: v for k, v in data.items()}).where(table.c.id == id)
        result = await self.middleware.run_in_executor(self.thread_pool, self.connection.execute, update)
        if result.rowcount != 1:
            raise RuntimeError('No rows were updated')

    @accepts(Str('name'), Any('id_or_filters'))
    async def delete(self, name, id_or_filters):
        """
        Delete an entry `id` in `name`.
        """
        table = self._get_table(name)

        delete = table.delete()
        if isinstance(id_or_filters, list):
            delete = delete.where(and_(*self._filters_to_queryset(id_or_filters, table, '')))
        else:
            delete = delete.where(table.c.id == id_or_filters)
        await self.middleware.run_in_executor(self.thread_pool, self.connection.execute, delete)
        return True

    @private
    async def sql(self, query, params=None):
        try:
            return [
                dict(v)
                for v in await self.middleware.run_in_executor(self.thread_pool, self.fetchall, query, params)
            ]
        except Exception as e:
            raise CallError(e)

    @accepts(List('queries'))
    def restore(self, queries):
        """
        Receives a list of SQL queries (usually a database dump)
        and executes it within a transaction.
        """
        return connection.dump_recv(queries)

    @accepts()
    def dump(self):
        """
        Dumps the database, returning a list of SQL commands.
        """
        # FIXME: This could return a few hundred KB of data,
        # we need to investigate a way of doing that in chunks.
        return connection.dump()

    @accepts()
    async def dump_json(self):
        models = []
        for model in django.apps.apps.get_models():
            if not model.__module__.startswith("freenasUI."):
                continue

            try:
                entries = await self.middleware.call("datastore.sql", f"SELECT * FROM {model._meta.db_table}")
            except CallError as e:
                self.logger.debug("%r", e)
                continue

            models.append({
                "table_name": model._meta.db_table,
                "verbose_name": str(model._meta.verbose_name),
                "fields": [
                    {
                        "name": field.column,
                        "verbose_name": str(field.verbose_name),
                        "database_type": field.db_type(connection),
                    }
                    for field in model._meta.get_fields()
                    if not field.is_relation
                ],
                "entries": entries,
            })

        return models


async def setup(middleware):
    await middleware.call("datastore.setup")
