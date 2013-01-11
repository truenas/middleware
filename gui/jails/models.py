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
from freenasUI.common.warden import Warden

class JailQuerySet(models.query.QuerySet):
    def iterator(self):
        wlist = Warden().list()
        for wj in wlist:
            tj = {}
            for k in wj:
                tj["jail_%s" % k] = wj[k]

            jm = self.model(**tj)
            yield jm

class JailManager(models.Manager):
    use_for_related_fields = True

    def __init__(self, qs_class=models.query.QuerySet):
        self.queryset_class = qs_class
        super(JailManager, self).__init__()

    def get_query_set(self):
        return JailQuerySet(self.model)

    def __getattr__(self, name):
        return getattr(self.get_query_set(), name)

class Jail(Model):
    objects = JailManager()

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
        verbose_name = _("Jail")
        verbose_name_plural = _("Jails") 

    class FreeAdmin:
        pass
