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

from django.conf.urls.defaults import patterns, url

# Active FreeNAS URLs

urlpatterns = patterns('storage.views',
    url(r'^home/$', 'home', name="storage_home"),
    url(r'^tasks/$', 'tasks', name="storage_tasks"),
    url(r'^volumes/$', 'volumes', name="storage_volumes"),
    url(r'^replications/$', 'replications', name="storage_replications"),
    url(r'^replications/public-key/$', 'replications_public_key', name="storage_replications_key"),
    url(r'^snapshots/$', 'snapshots', name="storage_snapshots"),
    url(r'^snapshots/data/$', 'snapshots_data', name="storage_snapshots_data"),
    url(r'^disks/$', 'disks_datagrid', name="storage_datagrid_disks"),
    url(r'^disks/json$', 'disks_datagrid_json', name="storage_datagrid_disks_json"),
    url(r'^datagrid/volume-(?P<vid>\d+)/status/$', 'volume_status', name="storage_volume_status"),
    url(r'^datagrid/volume-(?P<vid>\d+)/status/json/$', 'volume_status_json', name="storage_volume_status_json"),
    url(r'^dataset/create/(?P<fs>.+)/$', 'dataset_create', name="storage_dataset"),
    url(r'^dataset/delete/(?P<name>.+)/$', 'dataset_delete', name="storage_dataset_delete"),
    url(r'^dataset/edit/(?P<dataset_name>.+)/$', 'dataset_edit', name="storage_dataset_edit"),
    url(r'^zvol/create/(?P<volume_name>.+)/$', 'zvol_create', name="storage_zvol"),
    url(r'^zvol/delete/(?P<name>.+)/$', 'zvol_delete', name="storage_zvol_delete"),
    url(r'^snapshot/delete/(?P<dataset>[\-a-zA-Z0-9_/\.:]+)@(?P<snapname>[\-a-zA-Z0-9_\.:]+)/$', 'snapshot_delete', name="storage_snapshot_delete"),
    url(r'^snapshot/delete/bulk/$', 'snapshot_delete_bulk', name="storage_snapshot_delete_bulk"),
    url(r'^snapshot/rollback/(?P<dataset>[\-a-zA-Z0-9_/\.:]+)@(?P<snapname>[\-a-zA-Z0-9_\.:]+)/$', 'snapshot_rollback', name="storage_snapshot_rollback"),
    url(r'^snapshot/create/(?P<path>[\-a-zA-Z0-9_/\.:]+)/$', 'manualsnap', name="storage_manualsnap"),
    url(r'^snapshot/clone/(?P<snapshot>[\-a-zA-Z0-9_/\.:]+@[\-a-zA-Z0-9_\.:]+)/$', 'clonesnap', name="storage_clonesnap"),
    url(r'^mountpoint/permission/(?P<path>.+)/$', 'mp_permission', name="storage_mp_permission"),
    url(r'^wizard/$', 'wizard', name="storage_wizard"),
    url(r'^export/(?P<vid>\d+)/$', 'volume_export', name="storage_export"),
    url(r'^scrub/(?P<vid>\d+)/$', 'zpool_scrub', name="storage_scrub"),
    url(r'^import/$', 'volimport', name="storage_import"),
    url(r'^auto-import/$', 'volautoimport', name="storage_autoimport"),
    url(r'^periodic-snapshot/$', 'periodicsnap', name="storage_periodicsnap"),
    (r'volume/(?P<volume_id>\d+)/$', 'volume_disks'),
    url(r'^volume/zfs-edit/(?P<object_id>\d+)/$', 'zfsvolume_edit', name="storage_volume_edit"),
    url(r'^volume-(?P<vname>[^/]+)/disk/replace/$', 'geom_disk_replace', name="storage_geom_disk_replace"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/replace/(?P<label>.+)/$', 'zpool_disk_replace', name="storage_zpool_disk_replace"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/detach/(?P<label>.+)/$', 'disk_detach', name="storage_disk_detach"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/offline/(?P<label>.+)/$', 'disk_offline', name="storage_disk_offline"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/remove/(?P<label>.+)/$', 'zpool_disk_remove', name="storage_zpool_disk_remove"),
    url(r'^get_volumes/$', 'get_volumes', name="get_volumes"),
    url(r'^multipath/status/$', 'multipath_status', name="storage_multipath_status"),
    url(r'^multipath/status/json/$', 'multipath_status_json', name="storage_multipath_status_json"),
    )

