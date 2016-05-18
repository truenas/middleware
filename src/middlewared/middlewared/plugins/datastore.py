from middlewared.service import Service

import os
import sys

sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

from django.core import serializers
# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()


class DatastoreService(Service):

    def _filters_to_queryset(self, filters):
        opmap = {
            '=': 'exact',
            '>': 'gt',
            '>=': 'gte',
            '<': 'lt',
            '<=': 'lte',
        }

        rv = {}
        for f in filters:
            if len(f) == 3:
                name, op, value = f
                if op not in opmap:
                    raise Exception("Invalid operation {0}".format(op))
                rv['{0}__{1}'.format(name, opmap[op])] = value
            else:
                raise Exception("Invalid filter {0}".format(f))
        return rv

    def query(self, name, filters=None):
        app, model = name.split('.', 1)
        model = cache.get_model(app, model)

        qs = model.objects.all()
        if filters:
            qs = qs.filter(**self._filters_to_queryset(filters))

        return serializers.serialize('json', qs)
