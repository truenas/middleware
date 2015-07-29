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
import copy
import errno
import logging
import six

from django.db import models
from django.db.models import signals
from django.db.models.fields.related import ForeignKey
from django.db.models.base import ModelBase

from freenasUI.freeadmin.apppool import appPool
from freenasUI.middleware.exceptions import MiddlewareError, ValidationError

# FIXME: Backward compatible
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


class FieldMiddlewareMapping(object):

    def __init__(self, tuples):
        self.__field = {}
        self.__middleware = {}
        for key, val in tuples:
            keylist = self.__to_list(key)
            vallist = self.__to_list(val)

            for k in keylist:
                self.__field[k] = val

            for v in vallist:
                self.__middleware[v] = keylist

    def __to_list(self, key):
        if isinstance(key, (str, unicode)):
            key = [key]
        elif not isinstance(key, (list, tuple)):
            raise ValueError(
                "Invalid type for %r: %s" % (key, type(key).__name__)
            )
        return key

    def get_field_to_middleware(self, field):
        return self.__field.get(field, None)

    def get_middleware_to_field(self, field):
        return self.__middleware.get(field, [])


FMM = {
    'bsdgroups': FieldMiddlewareMapping((
        ('bsdgrp_group', 'name'),
        ('bsdgrp_builtin', 'builtin'),
        (('bsdgrp_gid', 'id'), 'id'),
        ('bsdgrp_sudo', 'sudo'),
    )),
    'bsdusers': FieldMiddlewareMapping((
        (('bsdusr_uid', 'id'), 'id'),
        ('bsdusr_username', 'username'),
        ('bsdusr_unixhash', 'unixhash'),
        ('bsdusr_smbhash', 'smbhash'),
        ('bsdusr_group', 'group'),
        ('bsdusr_home', 'home'),
        ('bsdusr_shell', 'shell'),
        ('bsdusr_full_name', 'full_name'),
        ('bsdusr_builtin', 'builtin'),
        ('bsdusr_email', 'email'),
        ('bsdusr_password_disabled', 'password_disabled'),
        ('bsdusr_locked', 'locked'),
        ('bsdusr_sudo', 'sudo'),
    )),
}


MIDDLEWARE_MODEL_METHODS = {
    'bsdgroups': {
        'query': 'groups.query',
        'add': 'groups.create',
        'delete': 'groups.delete',
        'update': 'groups.update',
    },
    'bsdusers': {
        'query': 'users.query',
        'add': 'users.create',
        'delete': 'users.delete',
        'update': 'users.update',
    }
}


def get_middleware_methods(model):
    methods = MIDDLEWARE_MODEL_METHODS.get(model._meta.model_name)
    if methods is None:
        raise NotImplementedError("RPC methods for '%s' not defined'" % (
            model._meta.model_name,
        ))
    return methods


class NewQuery(object):
    """Required by tastypie"""

    query_terms = set([
        'gt', 'in', 'month', 'isnull', 'endswith', 'week_day', 'year', 'regex',
        'gte', 'contains', 'lt', 'startswith', 'iendswith', 'icontains',
        'iexact', 'exact', 'day', 'minute', 'search', 'hour', 'iregex',
        'second', 'range', 'istartswith', 'lte'
    ])


class NewQuerySet(object):

    def __init__(self, model, **kwargs):
        self.model = model
        self._result_cache = None
        self._filters = []
        self._fmm = FMM.get(model._meta.model_name)
        if model._meta.ordering:
            self._sort = self._transform_order(*model._meta.ordering)
        else:
            self._sort = None
        self.query = NewQuery()

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

    def _clone(self, klass=None, **kwargs):
        if klass is None:
            klass = self.__class__
        c = klass(model=self.model)
        c._filters = copy.copy(self._filters)
        c._sort = copy.copy(self._sort)
        return c

    def _fetch_all(self):
        if self._result_cache is None:
            self._result_cache = list(self.iterator())

    def all(self):
        self._fetch_all()
        return self

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

            if self._fmm:
                field = self._fmm.get_field_to_middleware(key)
                if not field:
                    raise NotImplementedError("Field '%s' not mapped" % key)
            else:
                field = key

            if _filter == 'exact':
                self._filters.append(
                    (field, '=' if not opposite else '!=', val)
                )
            else:
                raise NotImplementedError(
                    "Filter '%s' not implemented" % _filter
                )

        return self

    def get(self, *args, **kwargs):
        self.filter(*args, **kwargs)
        self._fetch_all()
        if len(self._result_cache) == 0:
            raise self.model.DoesNotExist
        if len(self._result_cache) > 1:
            raise self.model.MultipleObjectsReturned
        return self._result_cache[0]

    def iterator(self):
        from freenasUI.middleware.connector import connection as dispatcher
        methods = get_middleware_methods(self.model)
        method = methods.get('query')
        if method is None:
            raise NotImplementedError(
                "RPC query method for '%s' not defined'" % (
                    self.model._meta.model_name,
                )
            )

        options = {}
        if self._sort is not None:
            options['sort'] = self._sort

        for i in dispatcher.call_sync(method, self._filters, options):
            data = {}
            if not self._fmm:
                continue
            for key, val in i.items():
                for f in self._fmm.get_middleware_to_field(key):
                    mfield = self.model._meta.get_field(f)
                    if isinstance(mfield, ForeignKey):
                        data[f] = mfield.rel.to.objects.get(pk=val)
                    else:
                        data[f] = val

            yield self.model(**data)

    def _transform_order(self, *args):
        sort = []
        for i in args:
            if i.startswith('-'):
                key = i[1:]
                desc = True
            else:
                key = i
                desc = False

            if self._fmm:
                field = self._fmm.get_field_to_middleware(key)
                if field:
                    if desc:
                        sort.append('-{0}'.format(field))
                    else:
                        sort.append(field)
        return sort

    def order_by(self, *args):
        clone = self._clone()
        clone._sort = clone._transform_order(*args)
        return clone


class NewManager(models.Manager):

    def __init__(self, qs_class=NewQuerySet):
        self.queryset_class = qs_class
        super(NewManager, self).__init__()

    def get_queryset(self):
        return NewQuerySet(self.model)


class NewModel(Model):

    objects = NewManager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        from freenasUI.middleware.connector import connection as dispatcher
        methods = get_middleware_methods(self)
        method = methods.get('delete')
        if method is None:
            raise NotImplementedError(
                "RPC delete method for '%s' not defined'" % (
                    self._meta.model_name,
                )
            )

        task = dispatcher.call_task_sync(method, [self.id])
        if task['state'] != 'FINISHED':
            raise MiddlewareError(task['error']['message'])

    def save(self, *args, **kwargs):
        from freenasUI.middleware.connector import connection as dispatcher
        methods = get_middleware_methods(self)

        if self.id is not None:
            mname = 'update'
            method_args = [self.id]
            updated = True
        else:
            mname = 'add'
            method_args = []
            updated = False

        method = methods.get(mname)
        if method is None:
            raise NotImplementedError("RPC %s method for '%s' not defined'" % (
                mname,
                self._meta.model_name,
            ))

        data = self.__dict__.copy()
        fmm = FMM.get(self._meta.model_name)
        if fmm:
            for key, val in data.items():
                field = fmm.get_field_to_middleware(key)
                if field == key:
                    continue
                if field:
                    data[field] = val
                del data[key]
        method_args.append(data)

        cls = origin = self.__class__
        using = None
        raw = None
        update_fields = data.keys()
        if cls._meta.proxy:
            cls = cls._meta.concrete_model
        meta = cls._meta

        if not meta.auto_created:
            signals.pre_save.send(
                sender=origin, instance=self, raw=raw, using=using,
                update_fields=update_fields
            )

        task = dispatcher.call_task_sync(method, method_args)
        if task['state'] != 'FINISHED':
            error = task['error']
            if error:
                extra = error.get('extra')
                fields = {}
                if extra and 'fields' in extra:
                    fmm = FMM.get(self._meta.model_name)
                    for field, errors in extra['fields'].items():
                        for key in fmm.get_middleware_to_field(field):
                            fields[key] = errors
                if not fields:
                    fields['__all__'] = [(errno.EINVAL, error['message'])]
                raise ValidationError(fields)
            raise ValueError(task['state'])

        if not meta.auto_created:
            signals.post_save.send(
                sender=origin, instance=self, created=(not updated),
                update_fields=update_fields, raw=raw, using=using,
            )
        return self
