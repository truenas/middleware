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

from dispatcher.rpc import RpcException
from freenasUI.freeadmin.apppool import appPool
from freenasUI.middleware.exceptions import MiddlewareError, ValidationError
from fnutils.query import wrap

# FIXME: Backward compatible
from .fields import (
    UserField, GroupField, PathField, MACField, Network4Field, Network6Field,
    ListField,
)

log = logging.getLogger('freeadmin.models')
MIDDLEWARE_MODEL_METHODS = {}


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


class Middleware(object):

    def __init__(self, model, klass):

        self.configstore = getattr(klass, 'configstore', False)
        self.default_filters = getattr(klass, 'default_filters', None)
        self.field_mapping = FieldMiddlewareMapping(
            getattr(klass, 'field_mapping', ()))
        self.provider_name = getattr(
            klass, 'provider_name', model._meta.model_name)

        self.middleware_methods = getattr(klass, 'middleware_methods', None)
        if self.middleware_methods is None:
            self.middlware_methods = {
                'query': '%s.query' % self.provider_name,
                'add': '%s.create' % self.provider_name,
                'delete': '%s.delete' % self.provider_name,
                'update': '%s.update' % self.provider_name,
            }


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

        if hasattr(new_class, 'Middleware'):
            new_class.add_to_class(
                '_middleware', Middleware(new_class, new_class.Middleware))

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


def get_middleware_methods(model):
    methods = model._middleware.middlware_methods
    if methods is not None:
        return methods
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
        self._filters = model._middleware.default_filters or []
        self._fmm = model._middleware.field_mapping
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
        return self._clone()

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
        c = self._clone()
        for key, val in kwargs.items():
            _filter = 'exact'
            if '__' in key:
                key, _filter = key.split('__')

            if key == 'pk':
                key = 'id'

            val = c.model._meta.get_field(key).to_python(val)

            if c._fmm:
                field = c._fmm.get_field_to_middleware(key)
                if not field:
                    raise NotImplementedError("Field '%s' not mapped" % key)
            else:
                field = key

            if _filter == 'exact':
                c._filters.append(
                    (field, '=' if not opposite else '!=', val)
                )
            elif _filter == 'regex':
                if opposite:
                    raise NotImplementedError(
                        "Exclude for regex not implemented"
                    )
                c._filters.append(
                    (field, '~', val)
                )
            elif _filter == 'in':
                c._filters.append(
                    (field, 'in' if not opposite else 'nin', val)
                )
            else:
                raise NotImplementedError(
                    "Filter '%s' not implemented" % _filter
                )

        return c

    def complex_filter(self, *args, **kwargs):
        log.debug("Unimplemented complex_filter called: %r - %r", args, kwargs)
        return self._clone()

    def get(self, *args, **kwargs):
        c = self._clone().filter(*args, **kwargs)
        c._fetch_all()
        if len(c._result_cache) == 0:
            raise c.model.DoesNotExist
        if len(c._result_cache) > 1:
            raise c.model.MultipleObjectsReturned
        return c._result_cache[0]

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

        for i in wrap(dispatcher.call_sync(method, self._filters, options)):
            data = {}
            if not self._fmm:
                continue
            forbreak = False
            for key, val in i.items():
                for f in self._fmm.get_middleware_to_field(key):
                    mfield = self.model._meta.get_field(f)
                    if isinstance(mfield, ForeignKey):
                        try:
                            data[f] = mfield.rel.to.objects.get(pk=val)
                        except mfield.rel.to.DoesNotExist:
                            log.error(
                                "%r(%d).%s has no foreign key '%d', skipping",
                                self.model, i.get('id'), f, val)
                            forbreak = True
                            break
                    else:
                        data[f] = val

                if forbreak:
                    break

            if forbreak:
                continue

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

    def select_related(self, *args):
        """This is a NOOP"""
        clone = self._clone()
        return clone

    def using(self, *args, **kwargs):
        return self._clone()

    def values_list(self, *args):
        self._fetch_all()
        rv = []
        for i in self._result_cache:
            rv.append(tuple([getattr(i, a) for a in args]))
        return rv


class NewManager(models.Manager):

    def __init__(self, qs_class=NewQuerySet):
        self.queryset_class = qs_class
        super(NewManager, self).__init__()

    def get_queryset(self):
        return self.queryset_class(self.model)


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

        task = dispatcher.call_task_sync(method, self.id)
        if task['state'] != 'FINISHED':
            raise MiddlewareError(task['error']['message'])

    def save(self, *args, **kwargs):

        cls = origin = self.__class__
        using = None
        raw = None
        update_fields = {}
        if cls._meta.proxy:
            cls = cls._meta.concrete_model
        meta = cls._meta

        if not meta.auto_created:
            signals.pre_save.send(
                sender=origin, instance=self, raw=raw, using=using,
                update_fields=update_fields
            )

        updated = self._save(*args, **kwargs)

        if not meta.auto_created:
            signals.post_save.send(
                sender=origin, instance=self, created=(not updated),
                update_fields=update_fields, raw=raw, using=using,
            )

        return self

    def _save_task_call(self, method, *method_args):
        from freenasUI.middleware.connector import connection as dispatcher

        try:
            log.debug("Calling task '%s' with args %r", method, method_args)
            task = dispatcher.call_task_sync(method, *method_args)
        except RpcException, e:
            raise ValidationError({
                '__all__': [(errno.EINVAL, i['message']) for i in e.extra] if e.extra else [(errno.EINVAL, str(e))],
            })

        if task['state'] != 'FINISHED':
            error = task['error']
            if error:
                extra = error.get('extra')
                fields = {}
                if extra and 'fields' in extra:
                    fmm = self._middleware.field_mapping
                    for field, errors in extra['fields'].items():
                        for key in fmm.get_middleware_to_field(field):
                            fields[key] = errors
                if not fields:
                    fields['__all__'] = [(errno.EINVAL, error['message'])]
                raise ValidationError(fields)
            raise ValueError(task['state'])
        return task

    def _save(self, *args, **kwargs):
        methods = get_middleware_methods(self)

        if self.id not in (None, ''):
            mname = 'update'
            method_args = [self.id]
            updated = True
        else:
            mname = 'add'
            method_args = []
            updated = False

        if 'method' in kwargs:
            method = kwargs.pop('method')
        else:
            method = methods.get(mname)

        if method is None:
            raise NotImplementedError("RPC %s method for '%s' not defined'" % (
                mname,
                self._meta.model_name,
            ))

        fmm = self._middleware.field_mapping
        data = kwargs.pop('data', {})
        if data:
            # Allow task to be submitted with custom data
            for key, val in data.items():
                field = fmm.get_field_to_middleware(key)
                if field is None:
                    continue
                if isinstance(val, NewModel):
                    data[field] = val.id
                else:
                    data[field] = val
                if field != key:
                    data.pop(key)
        else:
            # Transform model fields into data to be submitted
            for f in self._meta.fields:
                if not fmm:
                    data[f.name] = getattr(self, f.name)
                    continue
                # Do not send id for update task
                if f.name == 'id' and not updated:
                    continue
                field = fmm.get_field_to_middleware(f.name)
                if not field:
                    continue

                if isinstance(f, ForeignKey):
                    related = getattr(self, f.name)
                    data[field] = related.id if related is not None else None
                else:
                    data[field] = getattr(self, f.name)
        method_args.append(data)

        # Allow extra arguments to be passed to the task
        method_args.extend(kwargs.pop('extra_args', []))

        task = self._save_task_call(method, *method_args)

        if self.id is None and task['result'] is not None:
            self.id = task['result']

        return updated


class ConfigQuerySet(object):

    def __init__(self, model, **kwargs):
        self.model = model
        self.query = NewQuery()
        self._object = None

    def __getitem__(self, k):
        self._get_object()
        return self._object[0]

    def __iter__(self):
        self._get_object()
        yield self._object[0]

    def _clone(self, klass=None, **kwargs):
        if klass is None:
            klass = self.__class__
        return klass(model=self.model)

    def _get_object(self):
        if self._object is None:
            self._object = [self.model._load()]

    def get(self, *args, **kwargs):
        return self[0]

    def latest(self, *args, **kwargs):
        return self[0]

    def order_by(self, *args):
        return self._clone()

    def values(self, *args):
        c = self._clone()
        obj = c[0]
        data = {}
        for i in args:
            data[i] = getattr(obj, i)
        return [data]
