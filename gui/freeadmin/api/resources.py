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
from django.core.urlresolvers import reverse
from django.db.models import Q

from freenasUI.freeadmin.api.utils import (DojoModelResource,
    DjangoAuthentication)
from freenasUI.system.models import Sysctl
from freenasUI.storage.models import Disk


class SysctlResource(DojoModelResource):

    class Meta:
        queryset = Sysctl.objects.all()
        resource_name = 'sysctl'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']


class DiskResource(DojoModelResource):

    class Meta:
        queryset = Disk.objects.filter(
            disk_enabled=True,
            disk_multipath_name=''
            ).exclude(
                Q(disk_name__startswith='multipath') | Q(disk_name='')
            )
        resource_name = 'disk'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(DiskResource, self).dehydrate(bundle)
        bundle.data['_edit_url'] += '?deletable=false'
        bundle.data['_wipe_url'] = reverse('storage_disk_wipe', kwargs={
            'devname': bundle.obj.disk_name,
            })
        return bundle
