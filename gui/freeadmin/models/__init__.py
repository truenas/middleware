#+
# Copyright 2010 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import logging
import six

from django.db import models
from django.db.models import signals
from django.db.models.base import ModelBase

from freenasUI.common.log import log_traceback
from freenasUI.freeadmin.apppool import appPool

#FIXME: Backward compatible
from .fields import (
    UserField, GroupField, PathField, MACField, Network4Field, Network6Field
)

log = logging.getLogger('freeadmin.models')


class FreeModelBase(ModelBase):
    def __new__(cls, name, bases, attrs):
        from freenasUI.freeadmin.site import site

        bases = list(bases)
        appPool.hook_model_new(name, bases, attrs)
        new_class = ModelBase.__new__(cls, name, tuple(bases), attrs)
        if new_class._meta.abstract:
            pass
        elif hasattr(new_class, 'FreeAdmin'):
            site.register(new_class, freeadmin=new_class.FreeAdmin)

        return new_class


class Model(models.Model):
    __metaclass__ = FreeModelBase

    class Meta:
        abstract = True

    @models.permalink
    def get_add_url(self):
        return ('freeadmin_%s_%s_add' % (
            self._meta.app_label,
            self._meta.model_name,
            ), )

    @models.permalink
    def get_edit_url(self):
        return ('freeadmin_%s_%s_edit' % (
            self._meta.app_label,
            self._meta.model_name,
            ), (), {
            'oid': self.id,
            })

    @models.permalink
    def get_delete_url(self):
        return ('freeadmin_%s_%s_delete' % (
            self._meta.app_label,
            self._meta.model_name,
            ), (), {
            'oid': self.id,
            })

    @models.permalink
    def get_empty_formset_url(self):
        return ('freeadmin_%s_%s_empty_formset' % (
            self._meta.app_label,
            self._meta.model_name,
            ), )


FIELD2MIDDLEWARE = {
    'bsdgroups': {
        'bsdgrp_group': 'name',
        'bsdgrp_builtin': 'builtin',
        'bsdgrp_gid': 'id',
        'bsdgrp_sudo': 'sudo',
        'id': 'id',
    },
}

MIDDLEWARE2FIELD = {
    'bsdgroups': {
        'name': 'bsdgrp_group',
        'builtin': 'bsdgrp_builtin',
        'id': ('id', 'bsdgrp_gid'),
        'sudo': 'bsdgrp_sudo',
    },
}

MIDDLEWARE_MODEL_METHODS = {
    'bsdgroups': {
        'query': 'groups.query',
        'add': 'groups.create',
        'delete': 'groups.delete',
        'update': 'groups.update',
    }
}


def get_middleware_methods(model):
    methods = MIDDLEWARE_MODEL_METHODS.get(model._meta.model_name)
    if methods is None:
        raise NotImplementedError("RPC methods for '%s' not defined'" % (
            model._meta.model_name,
        ))
    return methods


class NewQuerySet(object):

    def __init__(self, model, **kwargs):
        self.model = model
        self._result_cache = None
        self._filters = []
        self._f2m = FIELD2MIDDLEWARE.get(
            self.model._meta.model_name
        )
        self._m2f = MIDDLEWARE2FIELD.get(
            self.model._meta.model_name
        )
        self._sort = None
        self._dir = None

    def __iter__(self):
        self._fetch_all()
        return iter(self._result_cache)

    def __getitem__(self, k):
        """
        Retrieves an item or slice from the set of results.
        """
        if not isinstance(k, (slice,) + six.integer_types):
            raise TypeError

        self._fetch_all()
        if self._result_cache is not None:
            return self._result_cache[k]

    def __len__(self):
        self._fetch_all()
        return len(self._result_cache)

    def _clone(self, klass=None, setup=False, **kwargs):
        if klass is None:
            klass = self.__class__
        c = klass(model=self.model)
        return c

    def _fetch_all(self):
        if self._result_cache is None:
            self._result_cache = list(self.iterator())

    def count(self):
        self._fetch_all()
        return len(self._result_cache)

    def exists(self):
        self._fetch_all()
        return len(self._result_cache) > 0

    def exclude(self, *args, **kwargs):
        return self._exclude_or_filter(True, *args, **kwargs)

    def filter(self, *args, **kwargs):
        return self._exclude_or_filter(False, *args, **kwargs)

    def _exclude_or_filter(self, opposite, *args, **kwargs):
        for key, val in kwargs.items():
            _filter = 'exact'
            if '__' in key:
                key, _filter = key.split('__')

            if key == 'pk':
                key = 'id'

            val = self.model._meta.get_field(key).to_python(val)

            if self._f2m:
                field = self._f2m.get(key)
                if field is None:
                    raise NotImplementedError("Field '%s' not mapped" % key)
            else:
                field = key

            if _filter == 'exact':
                self._filters.append(
                    (field, '=' if not opposite else '!=', val)
                )
            else:
                raise NotImplementedError("Filter '%s' not implemented" % _filter)

        return self

    def iterator(self):
        from freenasUI.middleware.connector import connection as dispatcher
        print self._filters
        methods = get_middleware_methods(self.model)
        method = methods.get('query')
        if method is None:
            raise NotImplementedError("RPC query method for '%s' not defined'" % (
                self.model._meta.model_name,
            ))

        options = {}
        if self._sort is not None:
            options['sort'] = self._sort
        if self._dir is not None:
            options['dir'] = self._dir

        for i in dispatcher.call_sync(method, self._filters, options):
            data = {}
            if self._m2f:
                for key, val in i.items():
                    field = self._m2f.get(key)
                    if isinstance(field, tuple):
                        for f in field:
                            data[f] = val
                    elif isinstance(field, str):
                        data[field] = val
                    elif field is None:
                        continue

            yield self.model(**data)

    def order_by(self, *args):
        for i in args:
            if i.startswith('-'):
                self._sort = i[1:]
                self._dir = 'desc'
            else:
                self._sort = i
                self._dir = 'asc'
        return self
