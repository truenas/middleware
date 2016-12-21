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

from django.conf.urls import patterns, url

from freenasUI.storage.forms import (
    AutoImportWizard, VolumeAutoImportForm, AutoImportChoiceForm,
    AutoImportDecryptForm, show_decrypt_condition
)

urlpatterns = patterns(
    'freenasUI.storage.views',
    url(r'^home/$', 'home', name="storage_home"),
    url(r'^tasks/$', 'tasks', name="storage_tasks"),
    url(r'^replications/$', 'replications', name="storage_replications"),
    url(r'^replications/public-key/$', 'replications_public_key', name="storage_replications_key"),
    url(r'^replications/keyscan/$', 'replications_keyscan', name="storage_replications_keyscan"),
    url(r'^replications/authtoken/$', 'replications_authtoken', name="storage_replications_authtoken"),
    url(r'^snapshots/$', 'snapshots', name="storage_snapshots"),
    url(r'^disks/editbulk/$', 'disk_editbulk', name="storage_disk_editbulk"),
    url(r'^disks/wipe/(?P<devname>[^/]+)/$', 'disk_wipe', name="storage_disk_wipe"),
    url(r'^disks/wipe/(?P<devname>[^/]+)/progress/$', 'disk_wipe_progress', name="storage_disk_wipe_progress"),
    url(r'^dataset/create/(?P<fs>.+)/$', 'dataset_create', name="storage_dataset"),
    url(r'^dataset/delete/(?P<name>.+)/$', 'dataset_delete', name="storage_dataset_delete"),
    url(r'^dataset/edit/(?P<dataset_name>.+)/$', 'dataset_edit', name="storage_dataset_edit"),
    url(r'^zvol/create/(?P<parent>.+)/$', 'zvol_create', name="storage_zvol"),
    url(r'^zvol/delete/(?P<name>.+)/$', 'zvol_delete', name="storage_zvol_delete"),
    url(r'^zvol/edit/(?P<name>.+)/$', 'zvol_edit', name="storage_zvol_edit"),
    url(r'^snapshot/delete/(?P<dataset>[\-a-zA-Z0-9_/\.: ]+)@(?P<snapname>[\-a-zA-Z0-9_\.: ]+)/$', 'snapshot_delete', name="storage_snapshot_delete"),
    url(r'^snapshot/delete/bulk/$', 'snapshot_delete_bulk', name="storage_snapshot_delete_bulk"),
    url(r'^snapshot/rollback/(?P<dataset>[\-a-zA-Z0-9_/\.: ]+)@(?P<snapname>[\-a-zA-Z0-9_\.: ]+)/$', 'snapshot_rollback', name="storage_snapshot_rollback"),
    url(r'^snapshot/create/(?P<fs>[\-a-zA-Z0-9_/\.: ]+)/$', 'manualsnap', name="storage_manualsnap"),
    url(r'^snapshot/clone/(?P<snapshot>[\-a-zA-Z0-9_/\.: ]+@[\-a-zA-Z0-9_\.: ]+)/$', 'clonesnap', name="storage_clonesnap"),
    url(r'^mountpoint/permission/(?P<path>.+)/$', 'mp_permission', name="storage_mp_permission"),
    url(r'^volumemanager/$', 'volumemanager', name="storage_volumemanager"),
    url(r'^volomemanager/progress/$', 'volumemanager_progress', name="storage_volumemanager_progress"),
    url(r'^volumemanager-zfs/$', 'volumemanager_zfs', name="storage_volumemanager_zfs"),
    url(r'^detach/(?P<vid>\d+)/$', 'volume_detach', name="storage_detach"),
    url(r'^scrub/(?P<vid>\d+)/$', 'zpool_scrub', name="storage_scrub"),
    url(r'^import/$', 'volimport', name="storage_import"),
    url(r'^import/progress$', 'volimport_progress', name='storage_volimport_progress'),
    url(r'^import/abort$', 'volimport_abort', name='storage_volimport_abort'),
    url(r'^auto-import/$', AutoImportWizard.as_view([AutoImportChoiceForm, AutoImportDecryptForm, VolumeAutoImportForm], condition_dict={'1': show_decrypt_condition}), name="storage_autoimport"),
    url(r'^volume/(?P<object_id>\d+)/upgrade/$', 'volume_upgrade', name="storage_volume_upgrade"),
    url(r'^volume/(?P<object_id>\d+)/create_passphrase/$', 'volume_create_passphrase', name="storage_volume_create_passphrase"),
    url(r'^volume/(?P<object_id>\d+)/change_passphrase/$', 'volume_change_passphrase', name="storage_volume_change_passphrase"),
    url(r'^volume/(?P<object_id>\d+)/lock/$', 'volume_lock', name="storage_volume_lock"),
    url(r'^volume/(?P<object_id>\d+)/unlock/$', 'volume_unlock', name="storage_volume_unlock"),
    url(r'^volume/(?P<object_id>\d+)/key/$', 'volume_key', name="storage_volume_key"),
    url(r'^volume/(?P<object_id>\d+)/key/download/$', 'volume_key_download', name="storage_volume_key_download"),
    url(r'^volume/(?P<object_id>\d+)/rekey/$', 'volume_rekey', name="storage_volume_rekey"),
    url(r'^volume/(?P<object_id>\d+)/recoverykey/add/$', 'volume_recoverykey_add', name="storage_volume_recoverykey_add"),
    url(r'^volume/(?P<object_id>\d+)/recoverykey/download/$', 'volume_recoverykey_download', name="storage_volume_recoverykey_download"),
    url(r'^volume/(?P<object_id>\d+)/recoverykey/remove/$', 'volume_recoverykey_remove', name="storage_volume_recoverykey_remove"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/replace/(?P<label>.+)/$', 'zpool_disk_replace', name="storage_zpool_disk_replace"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/detach/(?P<label>.+)/$', 'disk_detach', name="storage_disk_detach"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/offline/(?P<label>.+)/$', 'disk_offline', name="storage_disk_offline"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/online/(?P<label>.+)/$', 'disk_online', name="storage_disk_online"),
    url(r'^zpool-(?P<vname>[^/]+)/disk/remove/(?P<label>.+)/$', 'zpool_disk_remove', name="storage_zpool_disk_remove"),
    url(r'^multipath/status/$', 'multipath_status', name="storage_multipath_status"),
    url(r'^multipath/status/json/$', 'multipath_status_json', name="storage_multipath_status_json"),
    url(r'^vmwareplugin/datastores/$', 'vmwareplugin_datastores', name="storage_vmwareplugin_datastores"),
    url(r'^tasks/json/(?P<dataset>.+)/$', 'tasks_dataset_json', name="tasks_dataset_json"),
    url(r'^tasks/json/$', 'tasks_all_json', name="tasks_all_json"),
    url(r'^tasks/recursive/json/$', 'tasks_recursive_json', name="tasks_recursive_json"),
)
