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
from django.utils.translation import ugettext as _

from freenasUI import choices
from freenasUI.account.models import bsdUsers, bsdGroups
from freenasUI.freeadmin.api.utils import (
    DojoResource, DojoModelResource, DjangoAuthentication, DojoPaginator
)
from freenasUI.jails.models import Jails
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware import zfs
from freenasUI.network.models import (
    Interfaces, LAGGInterface, LAGGInterfaceMembers
)
from freenasUI.services.models import (
    iSCSITargetPortal, iSCSITargetExtent, iSCSITargetToExtent
)
from freenasUI.plugins.models import NullMountPoint
from freenasUI.sharing.models import NFS_Share
from freenasUI.system.models import CronJob, Rsync, SMARTTest
from freenasUI.storage.models import Disk, Replication, Scrub, Task, Volume

import logging

log = logging.getLogger('freeadmin.api.resources')


def _common_human_fields(bundle):
    for human in (
        'human_minute',
        'human_hour',
        'human_daymonth',
        'human_month',
        'human_dayweek',
    ):
        method = getattr(bundle.obj, "get_%s" % human, None)
        if not method:
            continue
        bundle.data[human] = getattr(bundle.obj, "get_%s" % human)()


class DiskResource(DojoModelResource):

    class Meta:
        queryset = Disk.objects.filter(
            disk_enabled=True,
            disk_multipath_name=''
        ).exclude(
            Q(disk_name__startswith='multipath') | Q(disk_name='')
        )
        resource_name = 'disk'
        paginator_class = DojoPaginator
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
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def _get_datasets(self, vol, datasets, uid):
        children = []
        attr_fields = ('total_si', 'avail_si', 'used_si', 'used_pct')
        for name, dataset in datasets.items():
            data = {
                'id': uid.next(),
                'name': name,
                'type': 'dataset',
                'status': vol.status,
                'mountpoint': dataset.mountpoint,
                'path': dataset.path,
            }
            for attr in attr_fields:
                data[attr] = getattr(dataset, attr)

            data['used'] = "%s (%s)" % (
                data['used_si'],
                data['used_pct'],
            )

            data['_dataset_delete_url'] = reverse(
                'storage_dataset_delete',
                kwargs={
                    'name': dataset.path,
                })
            data['_dataset_edit_url'] = reverse(
                'storage_dataset_edit',
                kwargs={
                    'dataset_name': dataset.path,
                })
            data['_dataset_create_url'] = reverse(
                'storage_dataset',
                kwargs={
                    'fs': dataset.path,
                })
            data['_permissions_url'] = reverse(
                'storage_mp_permission',
                kwargs={
                    'path': dataset.mountpoint,
                })
            data['_add_zfs_volume_url'] = reverse(
                'storage_zvol', kwargs={
                    'parent': dataset.path,
                })
            data['_manual_snapshot_url'] = reverse(
                'storage_manualsnap',
                kwargs={
                    'fs': dataset.path,
                })

            if dataset.children:
                _datasets = {}
                for child in dataset.children:
                    _datasets[child.name] = child
                data['children'] = self._get_datasets(vol, _datasets, uid)

            children.append(data)
        return children

    def dehydrate(self, bundle):
        bundle = super(VolumeResource, self).dehydrate(bundle)
        mp = bundle.obj.mountpoint_set.all()[0]

        bundle.data['name'] = bundle.obj.vol_name

        bundle.data['_detach_url'] = reverse(
            'storage_detach',
            kwargs={
                'vid': bundle.obj.id,
            })
        if bundle.obj.vol_fstype == 'ZFS':
            bundle.data['_scrub_url'] = reverse(
                'storage_scrub',
                kwargs={
                    'vid': bundle.obj.id,
                })
            bundle.data['_options_url'] = reverse(
                'storage_volume_edit',
                kwargs={
                    'object_id': mp.id,
                })
            bundle.data['_add_dataset_url'] = reverse(
                'storage_dataset',
                kwargs={
                    'fs': bundle.obj.vol_name,
                })
            bundle.data['_add_zfs_volume_url'] = reverse(
                'storage_zvol',
                kwargs={
                    'parent': bundle.obj.vol_name,
                })

        bundle.data['_permissions_url'] = reverse(
            'storage_mp_permission',
            kwargs={
                'path': mp.mp_path,
            })
        bundle.data['_status_url'] = "%s?id=%d" % (
            reverse('freeadmin_storage_volumestatus_datagrid'),
            bundle.obj.id,
        )

        if bundle.obj.vol_fstype == 'ZFS':
            bundle.data['_manual_snapshot_url'] = reverse(
                'storage_manualsnap',
                kwargs={
                    'fs': bundle.obj.vol_name,
                })
            bundle.data['_unlock_url'] = reverse(
                'storage_volume_unlock',
                kwargs={
                    'object_id': bundle.obj.id,
                })
            bundle.data['_download_key_url'] = reverse(
                'storage_volume_key',
                kwargs={
                    'object_id': bundle.obj.id,
                })
            bundle.data['_rekey_url'] = reverse(
                'storage_volume_rekey',
                kwargs={
                    'object_id': bundle.obj.id,
                })
            bundle.data['_add_reckey_url'] = reverse(
                'storage_volume_recoverykey_add',
                kwargs={'object_id': bundle.obj.id})
            bundle.data['_rem_reckey_url'] = reverse(
                'storage_volume_recoverykey_remove',
                kwargs={'object_id': bundle.obj.id})
            bundle.data['_create_passphrase_url'] = reverse(
                'storage_volume_create_passphrase',
                kwargs={'object_id': bundle.obj.id})
            bundle.data['_change_passphrase_url'] = reverse(
                'storage_volume_change_passphrase',
                kwargs={'object_id': bundle.obj.id})
            bundle.data['is_decrypted'] = bundle.obj.is_decrypted()

        attr_fields = ('total_si', 'avail_si', 'used_si', 'used_pct')
        for attr in attr_fields + ('status', ):
            bundle.data[attr] = getattr(mp, attr)

        if bundle.obj.is_decrypted():
            bundle.data['used'] = "%s (%s)" % (
                bundle.data['used_si'],
                bundle.data['used_pct'],
            )
        else:
            bundle.data['used'] = _("Locked")

        bundle.data['mountpoint'] = mp.mp_path

        if bundle.obj.vol_fstype == 'ZFS':
            uid = Uid(bundle.obj.id * 100)

            children = self._get_datasets(
                bundle.obj,
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

                data['_zvol_delete_url'] = reverse(
                    'storage_zvol_delete',
                    kwargs={
                        'name': name,
                    })
                data['_manual_snapshot_url'] = reverse(
                    'storage_manualsnap',
                    kwargs={
                        'fs': name,
                    })

                children.append(data)

            bundle.data['children'] = children
        return bundle


class VolumeStatusResource(DojoModelResource):

    class Meta:
        queryset = Volume.objects.all()
        resource_name = 'volumestatus'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']
        filtering = {
            'id': ('exact', ),
        }

    def dehydrate(self, bundle):
        bundle = super(VolumeStatusResource, self).dehydrate(bundle)
        bundle.data['name'] = bundle.obj.vol_name
        if bundle.obj.vol_fstype == 'ZFS':
            pool = notifier().zpool_parse(bundle.obj.vol_name)
            bundle.data['children'] = []
            bundle.data.update({
                'read': pool.data.read,
                'write': pool.data.write,
                'cksum': pool.data.cksum,
            })
            uid = Uid(bundle.obj.id * 100)
            for key in ('data', 'cache', 'spares', 'logs'):
                root = getattr(pool, key, None)
                if not root:
                    continue

                current = root
                parent = bundle.data
                tocheck = []
                while True:

                    if isinstance(current, zfs.Root):
                        data = {
                            'name': current.name,
                            'type': 'root',
                            'status': current.status,
                            'read': current.read,
                            'write': current.write,
                            'cksum': current.cksum,
                            'children': [],
                        }
                    elif isinstance(current, zfs.Vdev):
                        data = {
                            'name': current.name,
                            'type': 'vdev',
                            'status': current.status,
                            'read': current.read,
                            'write': current.write,
                            'cksum': current.cksum,
                            'children': [],
                        }
                    elif isinstance(current, zfs.Dev):
                        data = {
                            'name': current.devname,
                            'type': 'dev',
                            'status': current.status,
                            'read': current.read,
                            'write': current.write,
                            'cksum': current.cksum,
                            'children': [],
                        }
                        try:
                            disk = Disk.objects.order_by(
                                'disk_enabled'
                            ).filter(disk_name=current.disk)[0]
                            data['_disk_url'] = "%s?deletable=false" % (
                                disk.get_edit_url(),
                            )
                        except IndexError:
                            disk = None
                        if current.status == 'ONLINE':
                            data['_offline_url'] = reverse(
                                'storage_disk_offline',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })

                        if current.replacing:
                            data['_detach_url'] = reverse(
                                'storage_disk_detach',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })
                        else:
                            data['_replace_url'] = reverse(
                                'storage_zpool_disk_replace',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })
                        if current.parent.parent.name in (
                            'spares',
                            'cache',
                            'logs',
                        ):
                            data['_remove_url'] = reverse(
                                'storage_zpool_disk_remove',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })

                    else:
                        raise ValueError("Invalid node")

                    if key == 'data' and isinstance(current, zfs.Root):
                        parent.update(data)
                    else:
                        data['id'] = uid.next()
                        parent['children'].append(data)

                    for child in current:
                        tocheck.append((data, child))

                    if tocheck:
                        parent, current = tocheck.pop()
                    else:
                        break

        elif bundle.obj.vol_fstype == 'UFS':
            items = notifier().geom_disks_dump(bundle.obj)
            bundle.data['children'] = []
            bundle.data.update({
                'read': 0,
                'write': 0,
                'cksum': 0,
                'status': bundle.obj.status,
            })
            uid = Uid(bundle.obj.id * 100)
            for i in items:
                qs = Disk.objects.filter(disk_name=i['diskname']).order_by(
                    'disk_enabled')
                if qs:
                    i['_disk_url'] = "%s?deletable=false" % (
                        qs[0].get_edit_url(),
                    )
                if i['status'] == 'UNAVAIL':
                    i['_replace_url'] = reverse(
                        'storage_geom_disk_replace',
                        kwargs={'vname': bundle.obj.vol_name})
                i.update({
                    'id': uid.next(),
                    'read': 0,
                    'write': 0,
                    'cksum': 0,
                })
                bundle.data['children'].append(i)
        return bundle


class ScrubResource(DojoModelResource):

    class Meta:
        queryset = Scrub.objects.all()
        resource_name = 'scrub'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(ScrubResource, self).dehydrate(bundle)
        bundle.data['scrub_volume'] = bundle.obj.scrub_volume.vol_name
        _common_human_fields(bundle)
        return bundle


class ReplicationResource(DojoModelResource):

    class Meta:
        queryset = Replication.objects.all()
        resource_name = 'replication'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(ReplicationResource, self).dehydrate(bundle)
        bundle.data['ssh_remote_host'] = (
            bundle.obj.repl_remote.ssh_remote_hostname
        )
        return bundle


class TaskResource(DojoModelResource):

    class Meta:
        queryset = Task.objects.all()
        resource_name = 'task'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(TaskResource, self).dehydrate(bundle)
        if bundle.obj.task_repeat_unit == "daily":
            repeat = _('everyday')
        elif bundle.obj.task_repeat_unit == "weekly":
            wchoices = dict(choices.WEEKDAYS_CHOICES)
            labels = []
            for w in eval(bundle.obj.task_byweekday):
                labels.append(unicode(wchoices[str(w)]))
            days = ', '.join(labels)
            repeat = _('on every %(days)s') % {
                'days': days,
            }
        else:
            repeat = ''
        bundle.data['how'] = _(
            "From %(begin)s through %(end)s, every %(interv)s %(repeat)s") % {
                'begin': bundle.obj.task_begin,
                'end': bundle.obj.task_end,
                'interv': bundle.obj.get_task_interval_display(),
                'repeat': repeat,
            }
        bundle.data['keepfor'] = "%s %s" % (
            bundle.obj.task_ret_count,
            bundle.obj.task_ret_unit,
        )
        return bundle


class NFSShareResource(DojoModelResource):

    class Meta:
        queryset = NFS_Share.objects.all()
        resource_name = 'nfs_share'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(NFSShareResource, self).dehydrate(bundle)
        bundle.data['nfs_paths'] = bundle.obj.nfs_paths
        return bundle


class InterfacesResource(DojoModelResource):

    class Meta:
        queryset = Interfaces.objects.all()
        resource_name = 'interfaces'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(InterfacesResource, self).dehydrate(bundle)
        bundle.data['ipv4_addresses'] = bundle.obj.get_ipv4_addresses()
        bundle.data['ipv6_addresses'] = bundle.obj.get_ipv6_addresses()
        return bundle


class LAGGInterfaceResource(DojoModelResource):

    class Meta:
        queryset = LAGGInterface.objects.all()
        resource_name = 'lagginterface'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceResource, self).dehydrate(bundle)
        bundle.data['lagg_interface'] = unicode(bundle.obj)
        bundle.data['int_interface'] = bundle.obj.lagg_interface.int_interface
        bundle.data['int_name'] = bundle.obj.lagg_interface.int_name
        bundle.data['_edit_url'] = reverse(
            'freeadmin_network_interfaces_edit',
            kwargs={
                'oid': bundle.obj.lagg_interface.id,
            }) + '?deletable=false'
        bundle.data['_delete_url'] = reverse(
            'freeadmin_network_interfaces_delete',
            kwargs={
                'oid': bundle.obj.lagg_interface.id,
            })
        bundle.data['_members_url'] = reverse(
            'freeadmin_network_lagginterfacemembers_datagrid'
        ) + '?id=%d' % bundle.obj.id
        return bundle


class LAGGInterfaceMembersResource(DojoModelResource):

    class Meta:
        queryset = LAGGInterfaceMembers.objects.all()
        resource_name = 'lagginterfacemembers'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def build_filters(self, filters=None):
        if filters is None:
            filters = {}
        orm_filters = super(
            LAGGInterfaceMembersResource,
            self).build_filters(filters)
        lagggrp = filters.get("lagg_interfacegroup__id")
        if lagggrp:
            orm_filters["lagg_interfacegroup__id"] = lagggrp
        return orm_filters

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceMembersResource, self).dehydrate(bundle)
        bundle.data['lagg_interfacegroup'] = unicode(
            bundle.obj.lagg_interfacegroup
        )
        return bundle


class CronJobResource(DojoModelResource):

    class Meta:
        queryset = CronJob.objects.all()
        resource_name = 'cronjob'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(CronJobResource, self).dehydrate(bundle)
        _common_human_fields(bundle)
        return bundle


class RsyncResource(DojoModelResource):

    class Meta:
        queryset = Rsync.objects.all()
        resource_name = 'rsync'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(RsyncResource, self).dehydrate(bundle)
        _common_human_fields(bundle)
        return bundle


class SMARTTestResource(DojoModelResource):

    class Meta:
        queryset = SMARTTest.objects.all()
        resource_name = 'smarttest'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(SMARTTestResource, self).dehydrate(bundle)
        _common_human_fields(bundle)
        bundle.data['smarttest_type'] = bundle.obj.get_smarttest_type_display()
        return bundle


class ISCSIPortalResource(DojoModelResource):

    class Meta:
        queryset = iSCSITargetPortal.objects.all()
        resource_name = 'iscsitargetportal'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(ISCSIPortalResource, self).dehydrate(bundle)
        listen = ["%s:%s" % (
            p.iscsi_target_portalip_ip,
            p.iscsi_target_portalip_port,
        ) for p in bundle.obj.iscsitargetportalip_set.all()]
        bundle.data['iscsi_target_portalip_ips'] = listen
        return bundle


class ISCSITargetToExtentResource(DojoModelResource):

    class Meta:
        queryset = iSCSITargetToExtent.objects.all()
        resource_name = 'iscsitargettoextent'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(ISCSITargetToExtentResource, self).dehydrate(bundle)
        bundle.data['iscsi_target'] = bundle.obj.iscsi_target
        bundle.data['iscsi_extent'] = bundle.obj.iscsi_extent
        return bundle


class ISCSITargetExtentResource(DojoModelResource):

    class Meta:
        queryset = iSCSITargetExtent.objects.all()
        resource_name = 'iscsitargetextent'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(ISCSITargetExtentResource, self).dehydrate(bundle)
        if bundle.obj.iscsi_target_extent_type == 'Disk':
            disk = Disk.objects.get(id=bundle.obj.iscsi_target_extent_path)
            bundle.data['iscsi_target_extent_path'] = "/dev/%s" % disk.devname
        elif bundle.obj.iscsi_target_extent_type == 'ZVOL':
            bundle.data['iscsi_target_extent_path'] = "/dev/%s" % (
                bundle.data['iscsi_target_extent_path'],
            )
        return bundle


class BsdUserResource(DojoModelResource):

    class Meta:
        queryset = bsdUsers.objects.all().order_by(
            'bsdusr_builtin',
            'bsdusr_uid')
        resource_name = 'bsdusers'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(BsdUserResource, self).dehydrate(bundle)
        bundle.data['_passwd_url'] = (
            "%sbsdUserPasswordForm?deletable=false" % (
                bundle.obj.get_edit_url(),
            )
        )
        bundle.data['_email_url'] = "%sbsdUserEmailForm?deletable=false" % (
            bundle.obj.get_edit_url(),
        )
        bundle.data['_auxiliary_url'] = reverse(
            'account_bsduser_groups',
            kwargs={'object_id': bundle.obj.id})
        return bundle


class BsdGroupResource(DojoModelResource):

    class Meta:
        queryset = bsdGroups.objects.order_by('bsdgrp_builtin', 'bsdgrp_gid')
        resource_name = 'bsdgroups'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(BsdGroupResource, self).dehydrate(bundle)
        bundle.data['_members_url'] = reverse(
            'account_bsdgroup_members',
            kwargs={'object_id': bundle.obj.id})
        return bundle


class NullMountPointResource(DojoModelResource):

    class Meta:
        queryset = NullMountPoint.objects.all()
        resource_name = 'nullmountpoint'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(NullMountPointResource, self).dehydrate(bundle)
        bundle.data['mounted'] = bundle.obj.mounted
        return bundle


class JailsResource(DojoModelResource):

    class Meta:
        queryset = Jails.objects.all()
        resource_name = 'jails'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(JailsResource, self).dehydrate(bundle)

        bundle.data['name'] = bundle.obj.jail_host
        bundle.data['_jail_auto_url'] = reverse('jail_auto', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_checkup_url'] = reverse('jail_checkup', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_details_url'] = reverse('jail_details', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_export_url'] = reverse('jail_export', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_import_url'] = reverse('jail_import', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_options_url'] = reverse('jail_options', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_pkgs_url'] = reverse('jail_pkgs', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_pbis_url'] = reverse('jail_pbis', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_start_url'] = reverse('jail_start', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_stop_url'] = reverse('jail_stop', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_zfsmksnap_url'] = reverse('jail_zfsmksnap', kwargs={
            'id': bundle.obj.id
        })
        bundle.data['_jail_zfslistclone_url'] = reverse(
            'jail_zfslistclone',
            kwargs={
                'id': bundle.obj.id
            })
        bundle.data['_jail_zfslistsnap_url'] = reverse(
            'jail_zfslistsnap',
            kwargs={
                'id': bundle.obj.id
            })
        bundle.data['_jail_zfsclonesnap_url'] = reverse(
            'jail_zfsclonesnap',
            kwargs={
                'id': bundle.obj.id
            })
        bundle.data['_jail_zfscronsnap_url'] = reverse(
            'jail_zfscronsnap', kwargs={
                'id': bundle.obj.id
            })
        bundle.data['_jail_zfsrevertsnap_url'] = reverse(
            'jail_zfsrevertsnap', kwargs={
                'id': bundle.obj.id
            })
        bundle.data['_jail_zfsrmclone_url'] = reverse(
            'jail_zfsrmclonesnap', kwargs={
                'id': bundle.obj.id
            })
        bundle.data['_jail_zfsrmsnap_url'] = reverse('jail_zfsrmsnap', kwargs={
            'id': bundle.obj.id
        })

        return bundle
