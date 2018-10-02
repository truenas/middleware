from middlewared.service import CallError, Service
from middlewared.schema import accepts, Any, Bool, Dict, List, Ref, Str
from sqlite3 import OperationalError

import os
import sys
from itertools import chain

sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
from django.apps import apps
if not apps.ready:
    django.setup()

from django.apps import apps
from django.db import connection
from django.db.models import Q
from django.db.models.fields.related import ForeignKey, ManyToManyField

# FIXME: django sqlite3_ha backend uses a thread to sync queries to the
# standby node. That does not play very well with gevent+middleware
# if that "thread" is still running and the originating connection closes.
from freenasUI.freeadmin.sqlite3_ha import base as sqlite3_ha_base
sqlite3_ha_base.execute_sync = True

from middlewared.utils import django_modelobj_serialize


class DatastoreService(Service):

    class Config:
        private = True

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
                    raise ValueError("Invalid operation: {0}".format(op))
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
                raise ValueError("Invalid filter {0}".format(f))
        return rv

    def __get_model(self, name):
        """Helper method to get Model for given name
        e.g. network.interfaces -> Interfaces
        """
        app, model = name.split('.', 1)
        return apps.get_model(app, model)

    def __queryset_serialize(self, qs, extend=None, field_prefix=None):
        for i in qs:
            yield django_modelobj_serialize(self.middleware, i, extend=extend, field_prefix=field_prefix)

    @accepts(
        Str('name'),
        List('query-filters', default=None, null=True, register=True),
        Dict(
            'query-options',
            Str('extend', default=None, null=True),
            Dict('extra', additional_attrs=True),
            List('order_by', default=[]),
            Bool('count', default=False),
            Bool('get', default=False),
            Str('prefix'),
            default=None,
            null=True,
            register=True,
        ),
    )
    def query(self, name, filters=None, options=None):
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
        for i in self.__queryset_serialize(
            qs, extend=options.get('extend'), field_prefix=options.get('prefix')
        ):
            result.append(i)

        if options.get('get') is True:
            return result[0]

        return result

    @accepts(Str('name'), Ref('query-options'))
    def config(self, name, options=None):
        """
        Get configuration settings object for a given `name`.

        This is a shortcut for `query(name, {"get": true})`.
        """
        if options is None:
            options = {}
        options['get'] = True
        return self.query(name, None, options)

    @accepts(Str('name'), Dict('data', additional_attrs=True), Dict('options', Str('prefix')))
    def insert(self, name, data, options=None):
        """
        Insert a new entry to `name`.
        """
        data = data.copy()
        many_to_many_fields_data = {}
        options = options or {}
        prefix = options.get('prefix')
        model = self.__get_model(name)
        for field in chain(model._meta.fields, model._meta.many_to_many):
            if prefix:
                name = field.name.replace(prefix, '')
            else:
                name = field.name
            if name not in data:
                continue
            if isinstance(field, ForeignKey) and data[name] is not None:
                data[name] = field.rel.to.objects.get(pk=data[name])
            if isinstance(field, ManyToManyField):
                many_to_many_fields_data[field.name] = data.pop(name)
            else:

                # field.name is with prefix (if there's one) - we update data dict accordingly with db field names
                data[field.name] = data.pop(name)

        obj = model(**data)
        obj.save()

        for k, v in list(many_to_many_fields_data.items()):
            field = getattr(obj, k)
            field.add(*v)

        return obj.pk

    @accepts(Str('name'), Any('id'), Dict('data', additional_attrs=True), Dict('options', Str('prefix')))
    def update(self, name, id, data, options=None):
        """
        Update an entry `id` in `name`.
        """
        data = data.copy()
        many_to_many_fields_data = {}
        options = options or {}
        prefix = options.get('prefix')
        model = self.__get_model(name)
        obj = model.objects.get(pk=id)
        for field in chain(model._meta.fields, model._meta.many_to_many):
            if prefix:
                name = field.name.replace(prefix, '')
            else:
                name = field.name
            if name not in data:
                continue
            if isinstance(field, ForeignKey):
                data[name] = field.rel.to.objects.get(pk=data[name]) if data[name] is not None else None
            if isinstance(field, ManyToManyField):
                many_to_many_fields_data[field.name] = data.pop(name)
            else:
                setattr(obj, field.name, data.pop(name))

        obj.save()

        for k, v in list(many_to_many_fields_data.items()):
            field = getattr(obj, k)
            field.clear()
            field.add(*v)

        return obj.pk

    @accepts(Str('name'), Any('id_or_filters'))
    def delete(self, name, id_or_filters):
        """
        Delete an entry `id` in `name`.
        """
        model = self.__get_model(name)
        if isinstance(id_or_filters, list):
            qs = model.objects.all()
            qs.filter(*self._filters_to_queryset(id_or_filters, None)).delete()
        else:
            model.objects.get(pk=id_or_filters).delete()
        return True

    def sql(self, query, params=None):
        cursor = connection.cursor()
        try:
            if params is None:
                res = cursor.executelocal(query)
            else:
                res = cursor.executelocal(query, params)
            rv = [
                dict([
                    (res.description[i][0], value)
                    for i, value in enumerate(row)
                ])
                for row in cursor.fetchall()
            ]
        except OperationalError as err:
            raise CallError(err)
        finally:
            cursor.close()
        return rv

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
