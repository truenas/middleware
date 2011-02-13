#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.conf.urls.defaults import patterns, url
from freenasUI.storage.forms import *
from freenasUI.storage.views import *
from freenasUI.services.views import servicesToggleView as servicesToggleView

# Active FreeNAS URLs

urlpatterns = patterns('',
    (r'^$', storage),
    url(r'^home/$', home, name="storage_home"),
    url(r'^datagrid/volume-(?P<vid>\d+)/disks/$', disks_datagrid, name="storage_datagrid_disks"),
    url(r'^datagrid/volume-(?P<vid>\d+)/disks/json$', disks_datagrid_json, name="storage_datagrid_disks_json"),
    url(r'dataset/$', dataset_create),
    url(r'dataset2/$', dataset_create2, name="storage_dataset"),
    url(r'dataset/delete/(?P<object_id>\d+)/$', dataset_delete),
    url(r'dataset2/delete/(?P<object_id>\d+)/$', dataset_delete2, name="storage_dataset_delete"),
    url(r'mountpoint2/permission/(?P<object_id>\d+)/$', mp_permission2, name="storage_mp_permission"),
    (r'toggle/(?P<formname>\w+)/$', servicesToggleView),
    (r'wizard/$', VolumeWizard_wrapper),
    url(r'wizard2/$', wizard, name="storage_wizard"),
    (r'save/(?P<objtype>\w+)/$', storage),
    (r'volume/(?P<volume_id>\d+)/$', volume_disks),
    (r'mountpoint/permission/(?P<object_id>\d+)/$', mp_permission),
    (r'(?P<model_name>\w+)/delete/(?P<object_id>\d+)/$', generic_delete),
    (r'(?P<model_name>\w+)/edit/(?P<object_id>\d+)/$', generic_update),
    (r'(?P<model_name>\w+)/(?P<object_id>\d+)/$', generic_detail), # detail based on URL
    )

