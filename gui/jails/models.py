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
from django.utils.translation import ugettext_lazy as _
from django.db.models.options import Options

from freenasUI.freeadmin.models import Model
from freenasUI.common.warden import Warden, WARDEN_LIST_FLAGS_IDS

import logging

log = logging.getLogger('jails.jails')

class JailsQuerySet(models.query.QuerySet):
    def __init__(self, model=None, query=None, using=None):
        super(JailsQuerySet, self).__init__(model, query, using)
        self.__wlist = Warden().list(flags=WARDEN_LIST_FLAGS_IDS)
        self.__wcount = len(self.__wlist)

        tl = []
        self.__wlist = self.__order_by("id")
        for wj in self.__wlist:
            tj = self.__to_model_dict(wj)
            tl.append(tj)
        self.__wlist = tl

    def __ispk(self, k):
        ispk = False
        if (k == "id" or k == "-id"):
            ispk = True
        elif (k == "pk" or k == "-pk"):
            ispk = True
        return ispk

    def __key(self, k):
        key = k
        if self.__ispk(k):
            key = "id"
        return key

    def __to_model_dict(self, wj):
        tj = {}
        for k in wj:
            nk = self.__key(k)
            if not self.__ispk(k):
                nk = "jail_%s" % k
            tj[nk] = wj[k]

        return tj

    def iterator(self):
        for wj in self.__wlist:
            yield self.model(**wj)

    def count(self):
        return self.__wcount

    def __order_by(self, *field_names):
        for fn in field_names:
            fn = self.__key(fn)
            self.__wlist = sorted(self.__wlist, key=lambda k: k[fn]) 
        return self.__wlist

    def get(self, *args, **kwargs):
        results = []
        for wj in self.__wlist:

            found = 0
            count = len(kwargs) 
            for k in kwargs:
                key = self.__key(k)
                if self.__ispk(key):
                    kwargs[k] = int(kwargs[k])
                if wj.has_key(key) and wj[key] == kwargs[k]:
                    found += 1

            if found == count:
                results.append(wj)

        if len(results) == 0:
            raise self.model.DoesNotExist("Jail matching query does not exist")
        elif len(results) > 1:
            raise self.model.MultipleObjectsReturned ("Query returned multiple Jails")
        return self.model(**results[0])

class JailsManager(models.Manager):
    use_for_related_fields = True

    def __init__(self, qs_class=models.query.QuerySet):
        self.queryset_class = qs_class
        super(JailsManager, self).__init__()

    def get_query_set(self):
        return JailsQuerySet(self.model)

    def __getattr__(self, name):
        return getattr(self.get_query_set(), name)

class Jails(Model):
    objects = JailsManager()

    jail_host = models.CharField(max_length=120)
    jail_ip = models.CharField(max_length=255)
    jail_autostart = models.CharField(max_length=120)
    jail_status = models.CharField(max_length=120)
    jail_type = models.CharField(max_length=120)
    
    def delete(self):
        pass

    def save(self):
        pass

    class Meta:
        verbose_name = _("Jails")
        verbose_name_plural = _("Jails") 

    class FreeAdmin:
        pass

class JailsConfiguration(Model):

    jc_path = models.CharField(
        max_length=120,
        verbose_name=_("Jail Root"),
        help_text=_("Path where to store jail data")
        )

    class Meta:
        verbose_name = _("Jails Configuration")
        verbose_name_plural = _("Jails Configuration") 

    class FreeAdmin:
        pass
