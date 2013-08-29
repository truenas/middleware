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
import logging

from django.db.models.query import QuerySet

from freenasUI.common.warden import Warden

log = logging.getLogger('jails.queryset')


#
# XXX - Should implement order_by() and filter() methods
#
class JailsQuerySet(QuerySet):

    def __init__(self, model=None, query=None, using=None):
        super(JailsQuerySet, self).__init__(model, query, using)
        self.__wlist_cache = None
        self.__wcount_cache = None

    @property
    def __wlist(self):
        if self.__wlist_cache is None:
            try:
                wlist = Warden().list()
            except:
                wlist = []
            self.__wcount_cache = len(wlist)

            tl = []
            wlist = self.__order_by(wlist, "id")
            for wj in wlist:
                tj = self.__to_model_dict(wj)
                tl.append(tj)
            self.__wlist_cache = tl
        return self.__wlist_cache

    @property
    def __wcount(self):
        if self.__wcount_cache is None:
            self.__wcount_cache = len(self.__wlist)
        return self.__wcount_cache

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

    def __order_by(self, wlist, *fields):
        for fn in fields:
            fn = self.__key(fn)
            wlist = sorted(wlist, key=lambda k: k[fn])
        return wlist

    def order_by(self, *fields):
        models = []

        wlist = self.__wlist
        for fn in fields:
            fn = self.__key(fn)
            wlist = sorted(wlist, key=lambda k: k[fn])

        for wj in wlist:
            models.append(self.model(**wj))

        return models

    def latest(self, field_name=None):
        if field_name is not None:
            field_name = "-%s" % field_name
        #FIXME: not efficient
        models = self.order_by(field_name)
        if len(models) == 0:
            raise self.model.DoesNotExist
        else:
            return models[0]

    def get(self, *args, **kwargs):
        results = []
        for wj in self.__wlist:

            found = 0
            count = len(kwargs)
            for k in kwargs:
                key = self.__key(k)
                if self.__ispk(key):
                    kwargs[k] = int(kwargs[k])
                if key in wj and str(wj[key]) == str(kwargs[k]):
                    found += 1

            if found == count:
                results.append(wj)

        if len(results) == 0:
            raise self.model.DoesNotExist("Jail matching query does not exist")
        elif len(results) > 1:
            raise self.model.MultipleObjectsReturned(
                "Query returned multiple Jails"
            )
        return self.model(**results[0])

    #
    # Minimal filter() implementation....
    #
    def filter(self, *args, **kwargs):
        models = []
        results = []
        for wj in list(self.__wlist):

            found = 0
            count = len(kwargs)
            for k in kwargs:
                key = self.__key(k)
                if self.__ispk(key):
                    kwargs[k] = int(kwargs[k])
                if key in wj and str(wj[key]) == str(kwargs[k]):
                    found += 1

            if found != count:
                self.__wlist.remove(wj)

        return self
