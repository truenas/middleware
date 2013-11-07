#+
# Copyright 2013 iXsystems, Inc.
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
from django.db import models
from django.db.models.query import EmptyQuerySet
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.directoryservices.models import (
    ActiveDirectory,
    LDAP,
    NIS,
    NT4
)
from freenasUI.freeadmin.models import Model
from freenasUI.system.models import Settings

import logging
log = logging.getLogger('directoryservice.directoryservice')

class DirectoryServiceQuerySet(models.query.QuerySet):
    def __init__(self, model=None, query=None, using=None):
        super(DirectoryServiceQuerySet, self).__init__(model, query, using)
        self.__ds_list_cache = None
        self.__ds_count_cache = None

    @property
    def __ds_list(self):
        if self.__ds_list_cache is None:
            ds_list = []
            try:
                for ad in ActiveDirectory.objects.order_by("-id"):
                    ds_list.append(ad)
                for ldap in LDAP.objects.order_by("-id"):
                    ds_list.append(ldap)
                for nis in NIS.objects.order_by("-id"):
                    ds_list.append(nis)
                for nt4 in NT4.objects.order_by("-id"):
                    ds_list.append(nt4)
                   
            except:
                ds_list = []

            self.__ds_list_cache = ds_list
            self.__ds_count_cache = len(ds_list)

        return self.__ds_list_cache

    @property
    def __ds_count(self):
        if self.__ds_count_cache is None:
            self.__ds_count_cache = len(self.__ds_list)
        return self.__ds_count_cache

    def iterator(self):
        for ds in self.__ds_list:
            yield ds

    def count(self):
        return self.__ds_count

    def order_by(self, *fields):
        results = []

        ds_list = self.__ds_list
        for fn in fields:
            fn = self.__key(fn)
            ds_list = sorted(ds_list, key=lambda k: k[fn])

        for ds in ds_list:
            results.append(ds)

        return results

    def latest(self, field_name=None):
        if field_name is not None:
            field_name = "-%s" % field_name

        results = self.order_by(field_name)
        if len(results) == 0:
            raise self.model.DoesNotExist
        else:
            return results[0]

    def get(self, *args, **kwargs):
        results = []
        for ds in self.__ds_list:

            found = 0
            count = len(kwargs)
            for k in kwargs:
                if k in ds.__dict__ and ds.__dict__[k] == kwargs[k]:
                    found += 1

            if found == count:
                results.append(ds)

        if len(results) == 0:
            raise self.model.DoesNotExist("Directory service matching query does not exist")
        elif len(results) > 1:
            raise self.model.MultipleObjectsReturned(
                "Query returned multiple directory services"
            )
        return results[0]

    def filter(self, *args, **kwargs):
        for ds in list(self.__ds_list):

            found = 0
            count = len(kwargs)
            for k in kwargs:
                if k in ds.__dict__ and ds.__dict__[k] == kwargs[k]:
                    found += 1

            if found != count:
                self.__ds_list_cache.remove(ds)

        return self

class DirectoryServiceManager(models.Manager):
    use_for_related_fields = True

    def __init__(self, qs_class=models.query.QuerySet):
        self.queryset_class = qs_class
        super(DirectoryServiceManager, self).__init__()

    def get_query_set(self):
        return DirectoryServiceQuerySet(self.model)

    def __getattr__(self, name):
        return getattr(self.get_query_set(), name)


class DirectoryService(Model):
    objects = DirectoryServiceManager()

    class Meta:
        pass
