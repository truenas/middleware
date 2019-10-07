from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import operator
import re

from sqlalchemy import and_, create_engine, func, inspect, select, types
from sqlalchemy.sql import Alias

from middlewared.schema import accepts, Any, Bool, Dict, Int, List, Ref, Str
from middlewared.service import CallError, private, Service
from middlewared.sqlalchemy import Model
from middlewared.service_exception import MatchNotFound

from middlewared.plugins.config import FREENAS_DATABASE


"""
Mapping of tables to not to replicate to the remote side

It accepts a fields key which will then exclude these fields and not the
whole table.
"""
NO_SYNC_MAP = {
    'system_failover': {
        'fields': ['master'],
    },
}


def regexp(expr, item):
    reg = re.compile(expr, re.I)
    return reg.search(item) is not None


class DatastoreService(Service):

    class Config:
        private = True

    thread_pool = ThreadPoolExecutor(1)

    engine = None
    connection = None

    @private
    async def setup(self):
        await self.middleware.run_in_executor(self.thread_pool, self._setup)

    def _setup(self):
        if self.engine is not None:
            self.engine.dispose()

        if self.connection is not None:
            self.connection.close()

        self.engine = create_engine(f'sqlite:///{FREENAS_DATABASE}')

        self.connection = self.engine.connect()
        self.connection.connection.create_function("REGEXP", 2, regexp)
        self.connection.connection.execute("PRAGMA foreign_keys=ON")

    @private
    async def execute(self, *args):
        return await self.middleware.run_in_executor(self.thread_pool, self.connection.execute, *args)

    @private
    async def execute_write(self, stmt):
        compiled = stmt.compile(self.engine)

        sql = compiled.string
        binds = []
        for param in compiled.positiontup:
            bind = compiled.binds[param]
            value = bind.value
            bind_processor = compiled.binds[param].type.bind_processor(self.engine.dialect)
            if bind_processor:
                binds.append(bind_processor(value))
            else:
                binds.append(value)

        return await self.middleware.run_in_executor(self.thread_pool, self._execute_write, sql, binds)

    def _execute_write(self, sql, binds):
        result = self.connection.execute(sql, binds)
        self.middleware.call_hook_inline('datastore.post_execute_write', sql, binds)
        return result

    @private
    async def fetchall(self, *args):
        return await self.middleware.run_in_executor(self.thread_pool, self._fetchall, *args)

    def _fetchall(self, query, params=None):
        cursor = self.connection.execute(query, params or [])
        try:
            return cursor.fetchall()
        finally:
            cursor.close()

    def _get_table(self, name):
        return Model.metadata.tables[name.replace('.', '_').lower()]

    def _get_pk(self, table):
        return [col for col in table.c if col.primary_key][0]

    def _get_col(self, table, name, prefix=None):
        col = self._get_col_by_django_name(table, name)
        if col is not None:
            return col

        if prefix:
            col = self._get_col_by_django_name(table, prefix + name)
            if col is not None:
                return col

        raise KeyError(name)

    def _get_col_by_django_name(self, table, name):
        if name in table.c:
            return table.c[name]

        if f'{name}_id' in table.c:
            return table.c[f'{name}_id']

    def _get_relationships(self, table):
        for model in Model._decl_class_registry.values():
            if hasattr(model, "__tablename__") and model.__tablename__ == table.name:
                break
        else:
            raise RuntimeError("Could not find model for table %s" % table.name)

        return inspect(model).relationships

    def _filters_to_queryset(self, filters, table, prefix, aliases):
        opmap = {
            '=': operator.eq,
            '!=': operator.ne,
            '>': operator.gt,
            '>=': operator.ge,
            '<': operator.lt,
            '<=': operator.le,
            '~': lambda col, value: col.op('regexp')(value),
            'in': lambda col, value: col.in_(value),
            'nin': lambda col, value: ~col.in_(value),
            '^': lambda col, value: col.startswith(value),
            '$': lambda col, value: col.endswith(value),
        }

        rv = []
        for f in filters:
            if not isinstance(f, (list, tuple)):
                raise ValueError('Filter must be a list or tuple: {0}'.format(f))
            if len(f) == 3:
                name, op, value = f

                if '__' in name:
                    fk, name = name.split('__', 1)
                    col = self._get_col(aliases[list(self._get_col(table, fk, prefix).foreign_keys)[0]], name, '')
                else:
                    col = self._get_col(table, name, prefix)

                if op not in opmap:
                    raise ValueError('Invalid operation: {0}'.format(op))

                q = opmap[op](col, value)
                rv.append(q)
            elif len(f) == 2:
                op, value = f
                if op == 'OR':
                    or_value = None
                    for value in self._filters_to_queryset(value, table, prefix, aliases):
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

    async def _queryset_serialize(self, qs, table, aliases, relationships, extend, extend_context, field_prefix, select):
        if extend_context:
            extend_context_value = await self.middleware.call(extend_context)
        else:
            extend_context_value = None

        result = []
        for i, row in enumerate(qs):
            result.append(await self._serialize(
                row, table, aliases, relationships[i],
                extend, extend_context, extend_context_value, field_prefix, select
            ))

        return result

    async def _serialize(self, obj, table, aliases, relationships, extend, extend_context, extend_context_value,
                         field_prefix, select):
        data = self._serialize_row(obj, table, aliases, select)
        data.update(relationships)

        data = {self._strip_prefix(k, field_prefix): v for k, v in data.items()}

        if extend:
            if extend_context:
                data = await self.middleware.call(extend, data, extend_context_value)
            else:
                data = await self.middleware.call(extend, data)

        return data

    def _strip_prefix(self, k, field_prefix):
        return k[len(field_prefix):] if field_prefix and k.startswith(field_prefix) else k

    def _serialize_row(self, obj, table, aliases, select):
        data = {}

        for column in table.c:
            if select and column.name not in select:
                continue

            # aliases == {} when we are loading without relationships, let's leave fk values in that case
            if not column.foreign_keys or not aliases:
                data[column.name] = obj[column]

        for foreign_key, alias in aliases.items():
            column = foreign_key.parent

            if column.table != table:
                continue

            if not column.name.endswith('_id'):
                raise RuntimeError('Foreign key column must end with _id')

            data[column.name[:-3]] = (
                self._serialize_row(obj, alias, aliases, select)
                if obj[column] is not None and obj[self._get_pk(alias)] is not None
                else None
            )

        return data

    async def _fetch_many_to_many(self, table, rows):
        pk = self._get_pk(table)
        pk_values = [row[pk] for row in rows]

        relationships = [{} for row in rows]
        if pk_values:
            for relationship_name, relationship in self._get_relationships(table).items():
                # We can only join by single primary key
                assert len(relationship.synchronize_pairs) == 1
                assert len(relationship.secondary_synchronize_pairs) == 1

                local_pk, relationship_local_pk = relationship.synchronize_pairs[0]
                remote_pk, relationship_remote_pk = relationship.secondary_synchronize_pairs[0]

                assert local_pk == pk

                all_children_ids = set()
                pk_to_children_ids = defaultdict(set)
                for connection in await self.query(
                    relationship.secondary.name.replace('_', '.', 1),
                    [[relationship_local_pk.name, 'in', pk_values]],
                    {'relationships': False}
                ):
                    child_id = connection[relationship_remote_pk.name]

                    all_children_ids.add(child_id)
                    pk_to_children_ids[connection[relationship_local_pk.name]].add(child_id)

                all_children = {}
                if all_children_ids:
                    for child in await self.query(
                        relationship.target.name.replace('_', '.', 1),
                        [[remote_pk.name, 'in', all_children_ids]],
                    ):
                        all_children[child[remote_pk.name]] = child

                for i, row in enumerate(rows):
                    relationships[i][relationship_name] = [
                        all_children[child_id]
                        for child_id in pk_to_children_ids[row[pk]]
                        if child_id in all_children
                    ]

        return relationships

    @accepts(
        Str('name'),
        List('query-filters', default=None, null=True, register=True),
        Dict(
            'query-options',
            Bool('relationships', default=True),
            Str('extend', default=None, null=True),
            Str('extend_context', default=None, null=True),
            Str('prefix', default=None, null=True),
            Dict('extra', additional_attrs=True),
            List('order_by', default=[]),
            List('select', default=[]),
            Bool('count', default=False),
            Bool('get', default=False),
            Int('limit', default=0),
            null=True,
            register=True,
        ),
    )
    async def query(self, name, filters, options):
        """
        Query for items in a given collection `name`.

        `filters` is a list which each entry can be in one of the following formats:

            entry: simple_filter | conjuntion
            simple_filter: '[' attribute_name, OPERATOR, value ']'
            conjunction: '[' CONJUNCTION, '[' simple_filter (',' simple_filter)* ']]'

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

        # We do not want to make changes to original options
        # which might happen with "prefix"
        options = options.copy()

        aliases = {}
        if options['count']:
            qs = select([func.count(self._get_pk(table))])
        else:
            columns = list(table.c)
            from_ = table
            if options['relationships']:
                aliases = self._get_queryset_joins(table)
                for foreign_key, alias in aliases.items():
                    columns.extend(list(alias.c))
                    from_ = from_.outerjoin(alias, alias.c[foreign_key.column.name] == foreign_key.parent)

            qs = select(columns).select_from(from_)

        prefix = options['prefix']

        if filters:
            qs = qs.where(and_(*self._filters_to_queryset(filters, table, prefix, aliases)))

        if options['count']:
            return (await self.fetchall(qs))[0][0]

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

        result = await self.fetchall(qs)

        relationships = [{} for row in result]
        if options['relationships']:
            # This will only fetch many-to-many relationships for primary table, not for joins, but that's enough
            relationships = await self._fetch_many_to_many(table, result)

        result = await self._queryset_serialize(
            result,
            table, aliases, relationships, options['extend'], options['extend_context'], options['prefix'],
            options['select'],
        )

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
    async def insert(self, name, data, options):
        """
        Insert a new entry to `name`.
        """
        table = self._get_table(name)

        insert, relationships = self._extract_relationships(table, options['prefix'], data)

        for column in table.c:
            if column.default is not None:
                insert.setdefault(column.name, column.default.arg)
            if not column.nullable:
                if isinstance(column.type, (types.String, types.Text)):
                    insert.setdefault(column.name, '')

        await self.execute_write(table.insert().values(**insert))
        pk = (await self.fetchall('SELECT last_insert_rowid()'))[0][0]

        await self._handle_relationships(pk, relationships)

        return pk

    @accepts(Str('name'), Any('id'), Dict('data', additional_attrs=True), Dict('options', Str('prefix', default='')))
    async def update(self, name, id, data, options):
        """
        Update an entry `id` in `name`.
        """
        table = self._get_table(name)
        data = data.copy()

        for column in table.c:
            if column.foreign_keys:
                if column.name[:-3] in data:
                    data[column.name] = data.pop(column.name[:-3])

        update, relationships = self._extract_relationships(table, options['prefix'], data)

        if update:
            result = await self.execute_write(table.update().values(**update).where(self._get_pk(table) == id))
            if result.rowcount != 1:
                raise RuntimeError('No rows were updated')

        await self._handle_relationships(id, relationships)

    def _extract_relationships(self, table, prefix, data):
        relationships = self._get_relationships(table)

        insert = {}
        insert_relationships = []
        for k, v in data.items():
            relationship = relationships.get(prefix + k)
            if relationship:
                insert_relationships.append((relationship, v))
            else:
                insert[self._get_col(table, k, prefix).name] = v

        return insert, insert_relationships

    async def _handle_relationships(self, pk, relationships):
        for relationship, values in relationships:
            assert len(relationship.synchronize_pairs) == 1
            assert len(relationship.secondary_synchronize_pairs) == 1

            local_pk, relationship_local_pk = relationship.synchronize_pairs[0]
            remote_pk, relationship_remote_pk = relationship.secondary_synchronize_pairs[0]

            await self.execute_write(relationship_local_pk.table.delete().where(relationship_local_pk == pk))

            for value in values:
                await self.execute_write(relationship_local_pk.table.insert().values({
                    relationship_local_pk.name: pk,
                    relationship_remote_pk.name: value,
                }))

    @accepts(Str('name'), Any('id_or_filters'))
    async def delete(self, name, id_or_filters):
        """
        Delete an entry `id` in `name`.
        """
        table = self._get_table(name)

        delete = table.delete()
        if isinstance(id_or_filters, list):
            delete = delete.where(and_(*self._filters_to_queryset(id_or_filters, table, '', {})))
        else:
            delete = delete.where(self._get_pk(table) == id_or_filters)
        await self.execute_write(delete)
        return True

    @private
    async def get_backrefs(self, name):
        """
        Returns list of (datastore_name, column_name) for all tables that reference this table
        without being ON DELETE CASCADE / ON DELETE SET NULL.
        """
        table = self._get_table(name)

        result = []
        for other_table in Model.metadata.tables.values():
            for column in other_table.c:
                if column.foreign_keys:
                    foreign_key = list(column.foreign_keys)[0]
                    if foreign_key.column.table == table:
                        if foreign_key.ondelete is None:
                            result.append((
                                other_table.name.replace('_', '.', 1),
                                column.name[:-3] if column.name.endswith('_id') else column.name,
                            ))

        return result

    @private
    async def sql(self, query, *args):
        try:
            if query.strip().split()[0].upper() == 'SELECT':
                return [dict(row) for row in await self.fetchall(query, *args)]
            else:
                await self.execute(query, *args)
        except Exception as e:
            raise CallError(e)

    @accepts()
    async def dump_json(self):
        models = []
        for table, in await self.fetchall("SELECT name FROM sqlite_master WHERE type = 'table'"):
            try:
                entries = await self.middleware.call("datastore.sql", f"SELECT * FROM {table}")
            except CallError as e:
                self.logger.debug("%r", e)
                continue

            models.append({
                "table_name": table,
                "verbose_name": table,
                "fields": [
                    {
                        "name": row[1],
                        "verbose_name": row[1],
                        "database_type": row[2],
                    }
                    for row in await self.fetchall("PRAGMA table_info('%s');" % table)
                ],
                "entries": entries,
            })

        return models


async def setup(middleware):
    await middleware.call("datastore.setup")
