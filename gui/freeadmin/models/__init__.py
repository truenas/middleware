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
from django.db import models
from django.db.models.base import ModelBase

# FIXME: Backward compatible
from .fields import (
    UserField, GroupField, PathField, MACField, Network4Field, Network6Field,
    ListField,
)

log = logging.getLogger('freeadmin.models')
MIDDLEWARE_MODEL_METHODS = {}


class FreeModelBase(ModelBase):
    def __new__(cls, name, bases, attrs):

        bases = list(bases)
        new_class = ModelBase.__new__(cls, name, tuple(bases), attrs)
        if new_class._meta.abstract:
            pass

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
