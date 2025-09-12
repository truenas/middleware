from collections import defaultdict
from dataclasses import asdict, dataclass, field
from functools import cache
import re

from sqlalchemy import and_, func, select
from sqlalchemy.sql import Alias
from sqlalchemy.sql.expression import nullsfirst, nullslast

from middlewared.service import Service
from middlewared.service_exception import MatchNotFound
from middlewared.utils import filters
from .filter import FilterMixin
from .schema import SchemaMixin


filters_obj = filters()
do_select = filters_obj.do_select
validate_filters = filters_obj.validate_filters
validate_options = filters_obj.validate_options


def regexp(expr, item):
    reg = re.compile(expr, re.I)
    return reg.search(item) is not None


@dataclass(slots=True, kw_only=True)
class DatastoreQueryOptions:
    relationships: bool = True
    extend: str | None = None
    extend_context: str | None = None
    extend_fk: list | None = field(default_factory=list)
    prefix: str | None = None
    extra: dict = field(default_factory=dict)
    order_by: list = field(default_factory=list)
    select: list = field(default_factory=list)
    count: bool = False
    get: bool = False
    offset: int = 0
    limit: int = 0
    force_sql_filters: bool = False


class DatastoreService(Service, FilterMixin, SchemaMixin):

    class Config:
        private = True

    async def query(self, name, filters=None, options=None):
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

        filters = filters or []
        options = asdict(DatastoreQueryOptions(**(options or {})))

        validate_filters(filters)
        validate_options(options)

        prefix = options['prefix']
        extend_fk = options.get('extend_fk')
        fk_attrs = {}
        aliases = {}
        if options['count'] and not self._filters_contains_foreign_key(filters):
            qs = select([func.count(self._get_pk(table))])
        else:
            columns = list(table.c)
            from_ = table
            if options['relationships']:
                aliases = self._get_queryset_joins(table)
                for foreign_key, alias in aliases.items():
                    if extend_fk and foreign_key.parent.name.endswith('_id'):
                        fk = foreign_key.parent.name.removeprefix(prefix).removesuffix("_id")
                        if fk in extend_fk:
                            if _attrs := await self.middleware.call('datastore.get_service_config_attrs',
                                                                    foreign_key.column.table.name):
                                fk_attrs[fk] = _attrs
                    columns.extend(list(alias.c))
                    from_ = from_.outerjoin(alias, alias.c[foreign_key.column.name] == foreign_key.parent)

            if options['count']:
                qs = select([func.count(self._get_pk(table))]).select_from(from_)
            else:
                qs = select(columns).select_from(from_)

        if filters:
            qs = qs.where(and_(*self._filters_to_queryset(filters, table, prefix, aliases)))

        if options['count']:
            return (await self.middleware.call("datastore.fetchall", qs))[0][0]

        order_by = options['order_by']
        if order_by:
            # Do not change original order_by
            order_by = order_by[:]
            for i, order in enumerate(order_by):
                if order.startswith('nulls_first:'):
                    wrapper = nullsfirst
                    order = order[len('nulls_first:'):]
                elif order.startswith('nulls_last:'):
                    wrapper = nullslast
                    order = order[len('nulls_last:'):]
                else:
                    wrapper = lambda x: x  # noqa

                if order.startswith('-'):
                    order_by[i] = self._get_col(table, order[1:], prefix).desc()
                else:
                    order_by[i] = self._get_col(table, order, prefix)

                order_by[i] = wrapper(order_by[i])

            qs = qs.order_by(*order_by)

        if options['offset']:
            qs = qs.offset(options['offset'])

        if options['limit']:
            qs = qs.limit(options['limit'])

        result = await self.middleware.call("datastore.fetchall", qs)

        relationships = [{} for row in result]
        if options['relationships']:
            # This will only fetch many-to-many relationships for primary table, not for joins, but that's enough
            relationships = await self._fetch_many_to_many(table, result)

        result = await self._queryset_serialize(
            result,
            table, aliases, relationships, options['extend'], options['extend_context'], options['prefix'],
            options['select'], options['extra'], fk_attrs,
        )

        if options['get']:
            try:
                return result[0]
            except IndexError:
                raise MatchNotFound() from None

        return result

    async def config(self, name: str, options: dict | None = None):
        """
        Get configuration settings object for a given `name`.

        This is a shortcut for `query(name, {"get": true})`.
        """
        if options is None:
            options = dict()

        options.setdefault('get', True)
        validate_options(options)

        return await self.query(name, [], options)

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

    async def _queryset_serialize(
        self, qs, table, aliases, relationships, extend, extend_context, field_prefix, select, extra_options, fk_attrs,
    ):
        rows = []
        for i, row in enumerate(qs):
            rows.append(self._serialize(row, table, aliases, relationships[i], field_prefix, fk_attrs))

        if extend_context:
            extend_context_value = await self.middleware.call(extend_context, rows, extra_options)
        else:
            extend_context_value = None

        result = [
            await self._extend(data, extend, extend_context, extend_context_value, select)
            for data in rows
        ]

        for fk, attrs in fk_attrs.items():
            if not attrs['extend']:
                continue
            if attrs['extend_context']:
                extend_context_value = await self.middleware.call(attrs['extend_context'], rows, extra_options)
            else:
                extend_context_value = None
            for row in result:
                if fk in row:
                    row[fk] = await self._extend(row[fk],
                                                 attrs['extend'],
                                                 attrs['extend_context'],
                                                 extend_context_value,
                                                 {})
        return result

    def _serialize(self, obj, table, aliases, relationships, field_prefix, fk_attrs):
        data = self._serialize_row(obj, table, aliases)
        data.update(relationships)

        result = {self._strip_prefix(k, field_prefix): v for k, v in data.items()}
        # Check for nested data as a result of foreign keys
        for fk, attrs in fk_attrs.items():
            if not attrs['prefix']:
                continue
            if fk in result and isinstance(result[fk], dict):
                result[fk] = {self._strip_prefix(k, attrs['prefix']): v for k, v in result[fk].items()}
        return result

    async def _extend(self, data, extend, extend_context, extend_context_value, select):
        if extend:
            if extend_context:
                data = await self.middleware.call(extend, data, extend_context_value)
            else:
                data = await self.middleware.call(extend, data)

        if not select:
            return data
        else:
            return do_select([data], select)[0]

    def _strip_prefix(self, k, field_prefix):
        return k[len(field_prefix):] if field_prefix and k.startswith(field_prefix) else k

    def _serialize_row(self, obj, table, aliases):
        data = {}

        for column in table.c:
            # aliases == {} when we are loading without relationships, let's leave fk values in that case
            if not column.foreign_keys or not aliases:
                data[str(column.name)] = obj[column]

        for foreign_key, alias in aliases.items():
            column = foreign_key.parent

            if column.table != table:
                continue

            if not column.name.endswith('_id'):
                raise RuntimeError('Foreign key column must end with _id')

            data[column.name[:-3]] = (
                self._serialize_row(obj, alias, aliases)
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
                    {'relationships': False},
                ):
                    child_id = connection[relationship_remote_pk.name]

                    all_children_ids.add(child_id)
                    pk_to_children_ids[connection[relationship_local_pk.name]].add(child_id)

                all_children = {}
                if all_children_ids:
                    for child in await self.query(
                        relationship.target.name.replace('_', '.', 1),
                        [[remote_pk.name, 'in', all_children_ids]],
                        {'relationships': False},
                    ):
                        all_children[child[remote_pk.name]] = child

                for i, row in enumerate(rows):
                    relationships[i][relationship_name] = [
                        all_children[child_id]
                        for child_id in pk_to_children_ids[row[pk]]
                        if child_id in all_children
                    ]

        return relationships

    @cache
    def get_service_config_attrs(self, flat_table_name: str) -> dict:
        result = {}
        for service_name, service_obj in self.middleware.get_services().items():
            if service_obj._config and hasattr(service_obj._config, 'datastore'):
                if service_obj._config.datastore:
                    ds = service_obj._config.datastore.replace('.', '_').lower()
                    if ds == flat_table_name:
                        for attr in ['prefix', 'extend', 'extend_context']:
                            key = f'datastore_{attr}'
                            result[attr] = getattr(service_obj._config, key, None)
                        return result
        return result
