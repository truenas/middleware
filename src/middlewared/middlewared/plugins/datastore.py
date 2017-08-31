from middlewared.service import Service, private
from middlewared.schema import accepts, Any, Bool, Dict, Int, List, Ref, Str

import os
import sys

sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
from django.apps import apps
if not apps.ready:
    django.setup()

from django.apps import apps
from django.db import connection
from django.db.models import Q
from django.db.models.fields.related import ForeignKey

# FIXME: django sqlite3_ha backend uses a thread to sync queries to the
# standby node. That does not play very well with gevent+middleware
# if that "thread" is still running and the originating connection closes.
from freenasUI.freeadmin.sqlite3_ha import base as sqlite3_ha_base
sqlite3_ha_base.execute_sync = True

from middlewared.utils import django_modelobj_serialize


class DatastoreService(Service):

    def _filters_to_queryset(self, filters, field_prefix=None):
        opmap = {
            '=': 'exact',
            '!=': 'exact',
            '>': 'gt',
            '>=': 'gte',
            '<': 'lt',
            '<=': 'lte',
            '~': 'regex',
            'in': 'in',
            'nin': 'in',
        }

        rv = []
        for f in filters:
            if not isinstance(f, (list, tuple)):
                raise ValueError('Filter must be a list: {0}'.format(f))
            if len(f) == 3:
                name, op, value = f
                # id is special
                if field_prefix and name != 'id':
                    name = field_prefix + name
                if op not in opmap:
                    raise Exception("Invalid operation: {0}".format(op))
                q = Q(**{'{0}__{1}'.format(name, opmap[op]): value})
                if op in ('!=', 'nin'):
                    q.negate()
                rv.append(q)
            elif len(f) == 2:
                op, value = f
                if op == 'OR':
                    or_value = None
                    for value in self._filters_to_queryset(value, field_prefix=field_prefix):
                        if or_value is None:
                            or_value = value
                        else:
                            or_value |= value
                    rv.append(or_value)
                else:
                    raise ValueError('Invalid operation: {0}'.format(op))
            else:
                raise Exception("Invalid filter {0}".format(f))
        return rv

    def __get_model(self, name):
        """Helper method to get Model for given name
        e.g. network.interfaces -> Interfaces
        """
        app, model = name.split('.', 1)
        return apps.get_model(app, model)

    async def __queryset_serialize(self, qs, extend=None, field_prefix=None):
        result = await self.middleware.threaded(lambda: list(qs))
        for i in result:
            yield await django_modelobj_serialize(self.middleware, i, extend=extend, field_prefix=field_prefix)

    @accepts(
        Str('name'),
        List('query-filters', register=True),
        Dict(
            'query-options',
            Str('extend'),
            Dict('extra', additional_attrs=True),
            List('order_by'),
            Bool('count'),
            Bool('get'),
            Str('prefix'),
            register=True,
        ),
    )
    async def query(self, name, filters=None, options=None):
        """Query for items in a given collection `name`.

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
        model = self.__get_model(name)
        if options is None:
            options = {}
        else:
            # We do not want to make changes to original options
            # which might happen with "prefix"
            options = options.copy()

        qs = model.objects.all()

        extra = options.get('extra')
        if extra:
            qs = qs.extra(**extra)

        prefix = options.get('prefix')

        if filters:
            qs = qs.filter(*self._filters_to_queryset(filters, prefix))

        order_by = options.get('order_by')
        if order_by:
            if prefix:
                # Do not change original order_by
                order_by = order_by[:]
                for i, order in enumerate(order_by):
                    if order.startswith('-'):
                        order_by[i] = '-' + prefix + order[1:]
                    else:
                        order_by[i] = prefix + order
            qs = qs.order_by(*order_by)

        if options.get('count') is True:
            return qs.count()

        result = []
        async for i in self.__queryset_serialize(
            qs, extend=options.get('extend'), field_prefix=options.get('prefix')
        ):
            result.append(i)

        if options.get('get') is True:
            return result[0]

        return result

    @accepts(Str('name'), Ref('query-options'))
    async def config(self, name, options=None):
        """
        Get configuration settings object for a given `name`.

        This is a shortcut for `query(name, {"get": true})`.
        """
        if options is None:
            options = {}
        options['get'] = True
        return await self.query(name, None, options)

    @accepts(Str('name'), Dict('data', additional_attrs=True), Dict('options', Str('prefix')))
    async def insert(self, name, data, options=None):
        """
        Insert a new entry to `name`.
        """
        data = data.copy()
        options = options or {}
        prefix = options.get('prefix')
        model = self.__get_model(name)
        for field in model._meta.fields:
            if prefix:
                name = field.name.replace(prefix, '')
            else:
                name = field.name
            if name not in data:
                continue
            if isinstance(field, ForeignKey):
                data[name] = field.rel.to.objects.get(pk=data[name])
        if prefix:
            for k, v in list(data.items()):
                k_new = f'{prefix}{k}'
                data[k_new] = data.pop(k)
        obj = model(**data)
        await self.middleware.threaded(obj.save)
        return obj.pk

    @accepts(Str('name'), Any('id'), Dict('data', additional_attrs=True), Dict('options', Str('prefix')))
    async def update(self, name, id, data, options=None):
        """
        Update an entry `id` in `name`.
        """
        data = data.copy()
        options = options or {}
        prefix = options.get('prefix')
        model = self.__get_model(name)
        obj = await self.middleware.threaded(lambda oid: model.objects.get(pk=oid), id)
        for field in model._meta.fields:
            if prefix:
                name = field.name.replace(prefix, '')
            else:
                name = field.name
            if name not in data:
                continue
            if isinstance(field, ForeignKey):
                data[name] = field.rel.to.objects.get(pk=data[name])
        for k, v in list(data.items()):
            if prefix:
                k = f'{prefix}{k}'
            setattr(obj, k, v)
        await self.middleware.threaded(obj.save)
        return obj.pk

    @accepts(Str('name'), Any('id'))
    async def delete(self, name, id):
        """
        Delete an entry `id` in `name`.
        """
        model = self.__get_model(name)
        await self.middleware.threaded(lambda oid: model.objects.get(pk=oid).delete(), id)
        return True

    @private
    def sql(self, query, params=None):
        cursor = connection.cursor()
        rv = None
        try:
            if params is None:
                cursor.executelocal(query)
            else:
                cursor.executelocal(query, params)
            rv = cursor.fetchall()
        finally:
            cursor.close()
        return rv

    @private
    @accepts(List('queries'))
    def restore(self, queries):
        """
        Receives a list of SQL queries (usually a database dump)
        and executes it within a transaction.
        """
        return connection.dump_recv(queries)

    @private
    @accepts()
    def dump(self):
        """
        Dumps the database, returning a list of SQL commands.
        """
        # FIXME: This could return a few hundred KB of data,
        # we need to investigate a way of doing that in chunks.
        return connection.dump()
