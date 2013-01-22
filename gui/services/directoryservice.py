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
from django.db import models
from django.db.models.query import EmptyQuerySet
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.middleware.notifier import notifier
from freenasUI.freeadmin.models import Model
from freenasUI.services.models import ActiveDirectory, LDAP, NIS, NT4
from freenasUI.system.models import Settings

import logging
log = logging.getLogger('services.directoryservice')

class DirectoryServiceQuerySet(models.query.QuerySet):
    def __init__(self, model=None, query=None, using=None):
        settings = Settings.objects.order_by("-id")
        if settings:
            settings = settings[0]  

        type = settings.stg_directoryservice

        if type == 'activedirectory':
            super(DirectoryServiceQuerySet, self).__init__(ActiveDirectory, query, using)

        elif type == 'ldap':
            super(DirectoryServiceQuerySet, self).__init__(LDAP, query, using)

        elif type == 'nt4':
            super(DirectoryServiceQuerySet, self).__init__(NT4, query, using)

        elif type == 'nis':
            super(DirectoryServiceQuerySet, self).__init__(NIS, query, using)


class DirectoryServiceManager(models.Manager):
    use_for_related_fields = True

    def __init__(self, qs_class=models.query.QuerySet):
        self.queryset_class = qs_class
        super(DirectoryServiceManager, self).__init__()

    def get_query_set(self):
        settings = Settings.objects.order_by("-id")
        if settings:
            settings = settings[0]  

        type = settings.stg_directoryservice
        if type in ('activedirectory', 'ldap', 'nt4', 'nis'):
            return DirectoryServiceQuerySet(self.model)

        else:
            return EmptyQuerySet(self.model)

    def __getattr__(self, name):
        return getattr(self.get_query_set(), name)


class DirectoryService(Model):
    objects = DirectoryServiceManager()

    @staticmethod
    def __new__(cls, *args, **kwargs):
        new_class = None

        settings = Settings.objects.order_by("-id")
        if settings:
            settings = settings[0]  

        type = settings.stg_directoryservice

        if type == 'activedirectory':
            new_class = ActiveDirectory(*args, **kwargs)

        elif type == 'ldap':
            new_class = LDAP(*args, **kwargs)

        elif type == 'nt4':
            new_class = NT4(*args, **kwargs)

        elif type == 'nis':
            new_class = NIS(*args, **kwargs)

        return new_class

    class Meta:
        pass
