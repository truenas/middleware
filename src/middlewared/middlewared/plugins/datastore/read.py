from collections import defaultdict
import re

from sqlalchemy import and_, func, select
from sqlalchemy.sql import Alias
from sqlalchemy.sql.elements import UnaryExpression
from sqlalchemy.sql.expression import nullsfirst, nullslast
from sqlalchemy.sql.operators import desc_op, nullsfirst_op, nullslast_op

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, Str
from middlewared.service import Service
from middlewared.service_exception import MatchNotFound

from .filter import FilterMixin
from .schema import SchemaMixin


def regexp(expr, item):
    reg = re.compile(expr, re.I)
    return reg.search(item) is not None


class DatastoreService(Service, FilterMixin, SchemaMixin):

    class Config:
        private = True

    @accepts(
        Str('name'),
        List('query-filters', register=True),
        Dict(
            'query-options',
            Bool('relationships', default=True),
            Str('extend', default=None, null=True),
            Str('extend_context', default=None, null=True),
            Str('prefix', default=None, null=True),
            Dict('extra', additional_attrs=True),
            List('order_by'),
            List('select'),
            Bool('count', default=False),
            Bool('get', default=False),
            Int('offset', default=0),
            Int('limit', default=0),
            Bool('force_sql_filters', default=False),
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

            # FIXME: remove this after switching to SQLite 3.30
            changed = True
            while changed:
                changed = False
                for i, v in enumerate(order_by):
                    if isinstance(v, UnaryExpression) and v.modifier in (nullsfirst_op, nullslast_op):
                        if isinstance(v.element, UnaryExpression) and v.element.modifier == desc_op:
                            root_element = v.element.element
                        else:
                            root_element = v.element

                        order_by = order_by[:i] + [
                            {
                                nullsfirst_op: root_element != None,  # noqa
                                nullslast_op: root_element == None,  # noqa
                            }[v.modifier],
                            v.element,
                        ] + order_by[i + 1:]
                        changed = True
                        break

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
            options['select'], options['extra'],
        )

        if options['get']:
            try:
                return result[0]
            except IndexError:
                raise MatchNotFound()

        return result

    @accepts(Str('name'), Ref('query-options'))
    async def config(self, name, options):
        """
        Get configuration settings object for a given `name`.

        This is a shortcut for `query(name, {"get": true})`.
        """
        options['get'] = True
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
        self, qs, table, aliases, relationships, extend, extend_context, field_prefix, select, extra_options,
    ):
        rows = []
        for i, row in enumerate(qs):
            rows.append(self._serialize(row, table, aliases, relationships[i], field_prefix))

        if extend_context:
            extend_context_value = await self.middleware.call(extend_context, rows, extra_options)
        else:
            extend_context_value = None

        return [
            await self._extend(data, extend, extend_context, extend_context_value, select)
            for data in rows
        ]

    def _serialize(self, obj, table, aliases, relationships, field_prefix):
        data = self._serialize_row(obj, table, aliases)
        data.update(relationships)

        return {self._strip_prefix(k, field_prefix): v for k, v in data.items()}

    async def _extend(self, data, extend, extend_context, extend_context_value, select):
        if extend:
            if extend_context:
                data = await self.middleware.call(extend, data, extend_context_value)
            else:
                data = await self.middleware.call(extend, data)

        if not select:
            return data
        else:
            return {k: v for k, v in data.items() if k in select}

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
