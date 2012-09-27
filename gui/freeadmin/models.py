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
from collections import OrderedDict
from functools import update_wrapper
import json

from django import forms as dforms
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.base import ModelBase
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import get_template
from django.utils.translation import ugettext as _

from dojango.forms.models import inlineformset_factory
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.services.exceptions import ServiceFailed
from south.modelsinspector import add_introspection_rules

add_introspection_rules([], ["^(freenasUI\.)?freeadmin\.models\.UserField"])
add_introspection_rules([], ["^(freenasUI\.)?freeadmin\.models\.GroupField"])
add_introspection_rules([], ["^(freenasUI\.)?freeadmin\.models\.PathField"])


class UserField(models.CharField):
    def __init__(self, *args, **kwargs):
        self._exclude = kwargs.pop('exclude', [])
        kwargs['max_length'] = kwargs.get('max_length', 120)
        super(UserField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import UserField as UF
        defaults = {'form_class': UF, 'exclude': self._exclude}
        kwargs.update(defaults)
        return super(UserField, self).formfield(**kwargs)


class GroupField(models.CharField):
    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import GroupField as GF
        defaults = {'form_class': GF}
        kwargs.update(defaults)
        return super(GroupField, self).formfield(**kwargs)


class PathField(models.CharField):

    description = "A generic path chooser"

    def __init__(self, *args, **kwargs):
        self.abspath = kwargs.pop("abspath", True)
        self.includes = kwargs.pop("includes", [])
        kwargs['max_length'] = 255
        if kwargs.get('blank', False):
            kwargs['null'] = True
        super(PathField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        #FIXME: Move to top (causes cycle-dependency)
        from freenasUI.freeadmin.forms import PathField as PF
        defaults = {
            'form_class': PF,
            'abspath': self.abspath,
            'includes': self.includes,
            }
        kwargs.update(defaults)
        return super(PathField, self).formfield(**kwargs)


class FreeModelBase(ModelBase):
    def __new__(cls, name, bases, attrs):
        from freenasUI.freeadmin.site import site

        new_class = ModelBase.__new__(cls, name, bases, attrs)
        if new_class._meta.abstract:
            pass
        elif hasattr(new_class, 'FreeAdmin'):
            site.register(new_class, freeadmin=new_class.FreeAdmin)
        else:
            site.register(new_class)

        return new_class


class Model(models.Model):
    __metaclass__ = FreeModelBase

    class Meta:
        abstract = True

    @models.permalink
    def get_add_url(self):
        return ('freeadmin_%s_%s_add' % (
            self._meta.app_label,
            self._meta.module_name,
            ), )

    @models.permalink
    def get_edit_url(self):
        return ('freeadmin_%s_%s_edit' % (
            self._meta.app_label,
            self._meta.module_name,
            ), (), {
            'oid': self.id,
            })

    @models.permalink
    def get_delete_url(self):
        return ('freeadmin_%s_%s_delete' % (
            self._meta.app_label,
            self._meta.module_name,
            ), (), {
            'oid': self.id,
            })

    @models.permalink
    def get_empty_formset_url(self):
        return ('freeadmin_%s_%s_empty_formset' % (
            self._meta.app_label,
            self._meta.module_name,
            ), )
