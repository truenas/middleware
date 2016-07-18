from middlewared.service import Service

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
            '~', 'regex',
        }

        rv = []
        for f in filters:
            if len(f) == 3:
                name, op, value = f
                if op not in opmap:
                    raise Exception("Invalid operation {0}".format(op))
                q = Q(**{'{0}__{1}'.format(name, opmap[op]): value})
                if op == '!=':
                    q.negate()
                rv.append(q)
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
            yield self.django_modelobj_serialize(i, extend=extend)

    def query(self, name, filters=None, options=None):
        model = self.__get_model(name)
        if options is None:
            options = {}

        qs = model.objects.all()

        extra = options.get('extra')
        if extra:
            qs = qs.extra(extra)

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

    def insert(self, name, data):
        """
        Insert a new entry to 'name'.

        returns: primary key
        """
        model = self.__get_model(name)
        obj = model(**data)
        obj.save()
        return obj.pk
