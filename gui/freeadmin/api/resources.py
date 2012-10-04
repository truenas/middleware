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
from freenasUI.storage.models import Disk, Volume


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


class Uid(object):
    def __init__(self, start):
        self._start = start
        self._counter = start
    def next(self):
        number = self._counter
        self._counter += 1
        return number


class VolumeResource(DojoModelResource):

    class Meta:
        queryset = Volume.objects.all()
        resource_name = 'volume'
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def _get_datasets(self, datasets, uid):
        children = []
        attr_fields = ('total_si', 'avail_si', 'used_si')
        for name, dataset in datasets.items():
            data = {
                'id': uid.next(),
                'name': name,
                'type': 'dataset',
                'mountpoint': dataset.mountpoint,
            }
            for attr in attr_fields:
                data[attr] = getattr(dataset, attr)

            if dataset.children:
                _datasets = {}
                for child in dataset.children:
                    _datasets[child.name] = child
                data['children'] = self._get_datasets(_datasets, uid)

            children.append(data)
        return children

    def dehydrate(self, bundle):
        bundle = super(VolumeResource, self).dehydrate(bundle)

        bundle.data['name'] = bundle.obj.vol_name

        mp = bundle.obj.mountpoint_set.all()[0]
        attr_fields = ('total_si', 'avail_si', 'used_si')
        for attr in attr_fields + ('status', ):
            bundle.data[attr] = getattr(mp, attr)

        bundle.data['mountpoint'] = mp.mp_path

        uid = Uid(bundle.obj.id * 100)

        children = self._get_datasets(
            bundle.obj.get_datasets(hierarchical=True),
            uid=uid,
            )

        zvols = bundle.obj.get_zvols() or {}
        for name, zvol in zvols.items():
            data = {
                'id': uid.next(),
                'name': name,
                'status': mp.status,
                'type': 'zvol',
                'total_si': zvol['volsize'],
            }
            children.append(data)

        bundle.data['children'] = children
        return bundle
