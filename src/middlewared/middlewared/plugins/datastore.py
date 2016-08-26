from middlewared.service import Service
from middlewared.schema import accepts, Bool, Dict, List, Ref, Str

import os
import sys

sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from django.db.models import Q

from middlewared.utils import django_modelobj_serialize


class DatastoreService(Service):

    def _filters_to_queryset(self, filters):
        opmap = {
            '=': 'exact',
            '!=': 'exact',
            '>': 'gt',
            '>=': 'gte',
            '<': 'lt',
            '<=': 'lte',
            '~': 'regex',
        }

        rv = []
        for f in filters:
            if not isinstance(f, (list, tuple)):
                raise ValueError('Filter must be a list: {0}'.format(f))
            if len(f) == 3:
                name, op, value = f
                if op not in opmap:
                    raise Exception("Invalid operation: {0}".format(op))
                q = Q(**{'{0}__{1}'.format(name, opmap[op]): value})
                if op == '!=':
                    q.negate()
                rv.append(q)
            elif len(f) == 2:
                op, value = f
                if op == 'OR':
                    or_value = None
                    for value in self._filters_to_queryset(value):
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
        return cache.get_model(app, model)

    def __queryset_serialize(self, qs, extend=None):
        for i in qs:
            yield django_modelobj_serialize(self.middleware, i, extend=extend)

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
            register=True,
        ),
    )
    def query(self, name, filters=None, options=None):
        """Query for items in a given collection `name`.

        `filters` is a list which each entry can be in one of the following formats:

            entry: simple_filter | conjuntion
            simple_filter: '[' attribute_name, OPERATOR, value ']'
            conjunction: '[' CONJUNTION, '[' simple_filter (',' simple_filter)* ']]'

            OPERATOR: ('=' | '!=' | '>' | '>=' | '<' | '<=' | '~' )
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

        qs = model.objects.all()

        extra = options.get('extra')
        if extra:
            qs = qs.extra(**extra)

        if filters:
            qs = qs.filter(*self._filters_to_queryset(filters))

        order_by = options.get('order_by')
        if order_by:
            qs = qs.order_by(*order_by)

        if options.get('count') is True:
            return qs.count()

        result = list(self.__queryset_serialize(qs, extend=options.get('extend')))

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

    @accepts(Str('name'), Dict('data', additional_attrs=True))
    def insert(self, name, data):
        """
        Insert a new entry to `name`.
        """
        model = self.__get_model(name)
        obj = model(**data)
        obj.save()
        return obj.pk
