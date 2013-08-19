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
import logging
import re
import subprocess

from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms.models import inlineformset_factory
from django.utils.translation import ugettext as _

from freenasUI import choices
from freenasUI.account.forms import bsdUserCreationForm
from freenasUI.account.models import bsdUsers, bsdGroups
from freenasUI.api.utils import (
    DojoResource, DojoModelResource
)
from freenasUI.jails.models import (
    Jails, JailTemplate, NullMountPoint
)
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware import zfs
from freenasUI.services.models import (
    iSCSITargetPortal, iSCSITargetExtent, iSCSITargetToExtent
)
from freenasUI.plugins import availablePlugins, Plugin
from freenasUI.plugins.models import PLUGINS_INDEX, Configuration as PluginConf
from freenasUI.sharing.models import NFS_Share, NFS_Share_Path
from freenasUI.sharing.forms import NFS_SharePathForm
from freenasUI.storage.forms import VolumeManagerForm
from freenasUI.storage.models import Disk, Volume
from tastypie import fields
from tastypie.validation import FormValidation

log = logging.getLogger('api.resources')


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


class DiskResourceMixin(object):

    class Meta:
        queryset = Disk.objects.filter(
            disk_enabled=True,
            disk_multipath_name=''
        ).exclude(
            Q(disk_name__startswith='multipath') | Q(disk_name='')
        )
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(DiskResourceMixin, self).dehydrate(bundle)
        bundle.data['_edit_url'] += '?deletable=false'
        bundle.data['_wipe_url'] = reverse('storage_disk_wipe', kwargs={
            'devname': bundle.obj.disk_name,
        })
        bundle.data['_editbulk_url'] = reverse('storage_disk_editbulk')
        return bundle


class Uid(object):
    def __init__(self, start):
        self._start = start
        self._counter = start

    def next(self):
        number = self._counter
        self._counter += 1
        return number


class DatasetResource(DojoResource):

    name = fields.CharField(attribute='name')
    pool = fields.CharField(attribute='pool')
    used = fields.CharField(attribute='used')
    avail = fields.CharField(attribute='avail')
    refer = fields.CharField(attribute='refer')
    mountpoint = fields.CharField(attribute='mountpoint')

    class Meta:
        allowed_methods = ['get']
        object_class = zfs.ZFSDataset
        resource_name = 'storage/dataset'

    def obj_get_list(self, request=None, **kwargs):
        zfslist = zfs.list_datasets()
        return zfslist


class VolumeResourceMixin(object):

    class Meta:
        validation = FormValidation(form_class=VolumeManagerForm)

    def _get_datasets(self, bundle, vol, datasets, uid):
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

            if self.is_webclient(bundle.request):
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
                data['children'] = self._get_datasets(
                    bundle, vol, _datasets, uid
                )

            children.append(data)
        return children

    def hydrate(self, bundle):
        bundle = super(VolumeResourceMixin, self).hydrate(bundle)
        if 'layout' not in bundle.data:
            return bundle
        layout = bundle.data.pop('layout')
        for i, item in enumerate(layout):
            disks = item.get("disks")
            vtype = item.get("vdevtype")
            bundle.data['layout-%d-disks' % i] = '[%s]' % (
                ', '.join(['"%s"' % d for d in disks])
            )
            bundle.data['layout-%d-vdevtype' % i] = vtype
        bundle.data['layout-INITIAL_FORMS'] = 0
        bundle.data['layout-TOTAL_FORMS'] = i + 1
        return bundle

    def dehydrate(self, bundle):
        bundle = super(VolumeResourceMixin, self).dehydrate(bundle)
        mp = bundle.obj.mountpoint_set.all()[0]

        bundle.data['name'] = bundle.obj.vol_name

        is_decrypted = bundle.obj.is_decrypted()
        if bundle.obj.vol_fstype == 'ZFS':
            bundle.data['is_decrypted'] = is_decrypted

        if self.is_webclient(bundle.request):
            bundle.data['_detach_url'] = reverse(
                'storage_detach',
                kwargs={
                    'vid': bundle.obj.id,
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
                bundle.data['_manual_snapshot_url'] = reverse(
                    'storage_manualsnap',
                    kwargs={
                        'fs': bundle.obj.vol_name,
                    })
                if bundle.obj.vol_encrypt > 0:
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

        attr_fields = ('total_si', 'avail_si', 'used_si', 'used_pct')
        for attr in attr_fields + ('status', ):
            bundle.data[attr] = getattr(mp, attr)

        if is_decrypted:
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
                bundle,
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

                if self.is_webclient(bundle.request):
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
        allowed_methods = ['get']
        filtering = {
            'id': ('exact', ),
        }
        queryset = Volume.objects.all()
        resource_name = 'storage/volumestatus'

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
                        if (
                            current.parent.name == "logs" and
                            not current.name.startswith("stripe")
                        ):
                            data['_remove_url'] = reverse(
                                'storage_zpool_disk_remove',
                                kwargs={
                                    'vname': pool.name,
                                    'label': current.name,
                                })
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

                        """
                        Replacing might go south leaving multiple UNAVAIL disks
                        For that reason replace button should be enable even
                        for disks already under replacing subtree
                        """
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
                            if not current.parent.name.startswith("stripe"):
                                data['_detach_url'] = reverse(
                                    'storage_disk_detach',
                                    kwargs={
                                        'vname': pool.name,
                                        'label': current.name,
                                    })
                            else:
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


class ScrubResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(ScrubResourceMixin, self).dehydrate(bundle)
        bundle.data['scrub_volume'] = bundle.obj.scrub_volume.vol_name
        _common_human_fields(bundle)
        return bundle


class ReplicationResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(ReplicationResourceMixin, self).dehydrate(bundle)
        bundle.data['ssh_remote_host'] = (
            bundle.obj.repl_remote.ssh_remote_hostname
        )
        return bundle


class TaskResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(TaskResourceMixin, self).dehydrate(bundle)
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
        bundle.data['when'] = _(
            "From %(begin)s through %(end)s, %(repeat)s") % {
            'begin': bundle.obj.task_begin,
            'end': bundle.obj.task_end,
            'repeat': repeat,
        }
        bundle.data['interv'] = "every %s" % (
            bundle.obj.get_task_interval_display(),
        )
        bundle.data['keepfor'] = "%s %s" % (
            bundle.obj.task_ret_count,
            bundle.obj.task_ret_unit,
        )
        return bundle


class NFSShareResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(NFSShareResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['nfs_paths'] = u"%s" % ', '.join(bundle.obj.nfs_paths)
        else:
            bundle.data['nfs_paths'] = bundle.obj.nfs_paths

        for key in bundle.data.keys():
            if key.startswith('path_set'):
                del bundle.data[key]
        return bundle

    def hydrate(self, bundle):
        bundle = super(NFSShareResourceMixin, self).hydrate(bundle)
        if 'nfs_paths' not in bundle.data:
            return bundle
        nfs_paths = bundle.data.get('nfs_paths')
        for i, item in enumerate(nfs_paths):
            bundle.data['path_set-%d-path' % i] = item
            bundle.data['path_set-%d-id' % i] = ''
            bundle.data['path_set-%d-share' % i] = ''
        bundle.data['path_set-INITIAL_FORMS'] = 0
        bundle.data['path_set-TOTAL_FORMS'] = i + 1
        return bundle

    def is_form_valid(self, bundle, form):
        fset = inlineformset_factory(
            NFS_Share,
            NFS_Share_Path,
            form=NFS_SharePathForm,
            extra=0,
        )
        formset = fset(bundle.data, instance=bundle.obj, prefix="path_set")
        valid = formset.is_valid()
        errors = {}
        if not valid:
            #if formset._errors:
            #    errors.update(formset._errors)
            for form in formset:
                errors.update(form._errors)
        valid &= form.is_valid({'formset_nfs_share_path': formset})
        if errors:
            form._errors.update(errors)
        return valid

    def save_m2m(self, m2m_bundle):
        paths = []
        for path in m2m_bundle.obj.paths.all():
            if path.path not in m2m_bundle.data.get("nfs_paths", []):
                path.delete()
            else:
                paths.append(path.path)

        for path in m2m_bundle.data.get("nfs_paths", []):
            if path in paths:
                continue
            sp = NFS_Share_Path()
            sp.share = m2m_bundle.obj
            sp.path = path
            sp.save()
        return m2m_bundle


class InterfacesResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(InterfacesResourceMixin, self).dehydrate(bundle)
        bundle.data['ipv4_addresses'] = bundle.obj.get_ipv4_addresses()
        bundle.data['ipv6_addresses'] = bundle.obj.get_ipv6_addresses()
        return bundle


class LAGGInterfaceResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceResourceMixin, self).dehydrate(bundle)
        bundle.data['lagg_interface'] = unicode(bundle.obj)
        bundle.data['int_interface'] = bundle.obj.lagg_interface.int_interface
        bundle.data['int_name'] = bundle.obj.lagg_interface.int_name
        if self.is_webclient(bundle.request):
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


class LAGGInterfaceMembersResourceMixin(object):

    def build_filters(self, filters=None):
        if filters is None:
            filters = {}
        orm_filters = super(
            LAGGInterfaceMembersResourceMixin,
            self).build_filters(filters)
        lagggrp = filters.get("lagg_interfacegroup__id")
        if lagggrp:
            orm_filters["lagg_interfacegroup__id"] = lagggrp
        return orm_filters

    def dehydrate(self, bundle):
        bundle = super(LAGGInterfaceMembersResourceMixin, self).dehydrate(
            bundle
        )
        bundle.data['lagg_interfacegroup'] = unicode(
            bundle.obj.lagg_interfacegroup
        )
        return bundle


class CronJobResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(CronJobResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
        return bundle


class RsyncResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(RsyncResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
        return bundle


class SMARTTestResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(SMARTTestResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            _common_human_fields(bundle)
            bundle.data['smarttest_type'] = (
                bundle.obj.get_smarttest_type_display()
            )
        return bundle


class ISCSIPortalResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(ISCSIPortalResourceMixin, self).dehydrate(bundle)
        listen = ["%s:%s" % (
            p.iscsi_target_portalip_ip,
            p.iscsi_target_portalip_port,
        ) for p in bundle.obj.iscsitargetportalip_set.all()]
        bundle.data['iscsi_target_portalip_ips'] = listen
        return bundle


class ISCSITargetToExtentResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(ISCSITargetToExtentResourceMixin, self).dehydrate(
            bundle
        )
        bundle.data['iscsi_target'] = bundle.obj.iscsi_target
        bundle.data['iscsi_extent'] = bundle.obj.iscsi_extent
        return bundle


class ISCSITargetExtentResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(ISCSITargetExtentResourceMixin, self).dehydrate(bundle)
        if bundle.obj.iscsi_target_extent_type == 'Disk':
            disk = Disk.objects.get(id=bundle.obj.iscsi_target_extent_path)
            bundle.data['iscsi_target_extent_path'] = "/dev/%s" % disk.devname
        elif bundle.obj.iscsi_target_extent_type == 'ZVOL':
            bundle.data['iscsi_target_extent_path'] = "/dev/%s" % (
                bundle.data['iscsi_target_extent_path'],
            )
        return bundle


class BsdUserResourceMixin(object):

    class Meta:
        queryset = bsdUsers.objects.all().order_by(
            'bsdusr_builtin',
            'bsdusr_uid')
        validation = FormValidation(form_class=bsdUserCreationForm)

    def dehydrate(self, bundle):
        bundle = super(BsdUserResourceMixin, self).dehydrate(bundle)
        bundle.data['bsdusr_group'] = bundle.obj.bsdusr_group.bsdgrp_gid
        if self.is_webclient(bundle.request):
            if bundle.obj.bsdusr_builtin:
                bundle.data['_edit_url'] += '?deletable=false'
            bundle.data['_passwd_url'] = (
                "%sbsdUserPasswordForm?deletable=false" % (
                    bundle.obj.get_edit_url(),
                )
            )
            bundle.data['_email_url'] = (
                "%sbsdUserEmailForm?deletable=false" % (
                    bundle.obj.get_edit_url(),
                )
            )
            bundle.data['_auxiliary_url'] = reverse(
                'account_bsduser_groups',
                kwargs={'object_id': bundle.obj.id})
        return bundle


class BsdGroupResourceMixin(object):

    class Meta:
        queryset = bsdGroups.objects.order_by('bsdgrp_builtin', 'bsdgrp_gid')

    def dehydrate(self, bundle):
        bundle = super(BsdGroupResourceMixin, self).dehydrate(bundle)
        if self.is_webclient(bundle.request):
            bundle.data['_members_url'] = reverse(
                'account_bsdgroup_members',
                kwargs={'object_id': bundle.obj.id})
        return bundle


class NullMountPointResourceMixin(object):

    def dehydrate(self, bundle):
        bundle = super(NullMountPointResourceMixin, self).dehydrate(bundle)
        bundle.data['mounted'] = bundle.obj.mounted
        return bundle


class JailsResourceMixin(object):

    def dispatch_list(self, request, **kwargs):
        proc = subprocess.Popen(
            ["/usr/sbin/jls"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.__jls = proc.communicate()[0]
        return super(JailsResourceMixin, self).dispatch_list(request, **kwargs)

    def dehydrate(self, bundle):
        bundle = super(JailsResourceMixin, self).dehydrate(bundle)

        bundle.data['name'] = bundle.obj.jail_host
        try:
            reg = re.search(
                r'\s*?(\d+).*?\b%s\b' % bundle.obj.jail_host,
                self.__jls,
            )
            bundle.data['jid'] = int(reg.groups()[0])
        except:
            bundle.data['jid'] = None
        if self.is_webclient(bundle.request):
            bundle.data['_edit_url'] = reverse('jail_edit', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_storage_add_url'] = reverse(
                'jail_storage_add', kwargs={'jail_id': bundle.obj.id}
            )
            bundle.data['_upload_url'] = reverse('plugins_upload', kwargs={
                'jail_id': bundle.obj.id
            })
            bundle.data['_jail_export_url'] = reverse('jail_export', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_import_url'] = reverse('jail_import', kwargs={})
            bundle.data['_jail_start_url'] = reverse('jail_start', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_stop_url'] = reverse('jail_stop', kwargs={
                'id': bundle.obj.id
            })
            bundle.data['_jail_delete_url'] = reverse('jail_delete', kwargs={
                'id': bundle.obj.id
            })

        return bundle

class JailTemplateResource(DojoModelResource):

    class Meta:
        queryset = JailTemplate.objects.all()
        resource_name = 'jailtemplate'
        paginator_class = DojoPaginator
        authentication = DjangoAuthentication()
        include_resource_uri = False
        allowed_methods = ['get']

    def dehydrate(self, bundle):
        bundle = super(JailTemplateResource, self).dehydrate(bundle)
        bundle.data['jt_instances'] = bundle.obj.jt_instances
        bundle.data['_edit_url'] = reverse('jail_template_edit', kwargs={
            'id': bundle.obj.id
        })
        return bundle


class SnapshotResource(DojoResource):

    id = fields.CharField(attribute='filesystem')
    name = fields.CharField(attribute='name')
    filesystem = fields.CharField(attribute='filesystem')
    fullname = fields.CharField(attribute='fullname')
    refer = fields.CharField(attribute='refer')
    used = fields.CharField(attribute='used')
    mostrecent = fields.BooleanField(attribute='mostrecent')
    parent_type = fields.CharField(attribute='parent_type')

    class Meta:
        allowed_methods = ['get']
        object_class = zfs.Snapshot
        resource_name = 'storage/snapshot'

    def get_list(self, request, **kwargs):
        snapshots = notifier().zfs_snapshot_list()
        results = []
        for snaps in snapshots.values():
            results.extend(snaps)
        FIELD_MAP = {
            'used': 'used_bytes',
            'refer': 'refer_bytes',
            'extra': 'mostrecent',
        }
        for sfield in self._apply_sorting(request.GET):
            if sfield.startswith('-'):
                field = sfield[1:]
                reverse = True
            else:
                field = sfield
                reverse = False
            field = FIELD_MAP.get(field, field)
            results.sort(
                key=lambda item: getattr(item, field),
                reverse=reverse)
        paginator = self._meta.paginator_class(
            request,
            results,
            resource_uri=self.get_resource_uri(),
            limit=self._meta.limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )
        to_be_serialized = paginator.page()
        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        length = len(bundles)
        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(
            request,
            to_be_serialized
        )
        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset+length-1,
            len(results)
        )
        return response

    def dehydrate(self, bundle):
        bundle.data['extra'] = {
            'clone_url': reverse(
                'storage_clonesnap',
                kwargs={
                    'snapshot': bundle.obj.fullname,
                }),
            'rollback_url': reverse('storage_snapshot_rollback', kwargs={
                'dataset': bundle.obj.filesystem,
                'snapname': bundle.obj.name,
            }) if bundle.obj.mostrecent else None,
            'delete_url': reverse('storage_snapshot_delete', kwargs={
                'dataset': bundle.obj.filesystem,
                'snapname': bundle.obj.name,
            }),
        }
        return bundle


class AvailablePluginsResource(DojoResource):

    id = fields.CharField(attribute='id')
    name = fields.CharField(attribute='name')
    description = fields.CharField(attribute='description')
    version = fields.CharField(attribute='version')

    class Meta:
        object_class = Plugin
        resource_name = 'plugins/available'

    def get_list(self, request, **kwargs):
        conf = PluginConf.objects.latest('id')
        if conf and conf.collectionurl:
            url = conf.collectionurl
        else:
            url = PLUGINS_INDEX
        try:
            results = availablePlugins.get_remote(url=url)
        except Exception, e:
            log.debug("Failed to fetch remote: %s", e)
            results = []
        for sfield in self._apply_sorting(request.GET):
            if sfield.startswith('-'):
                field = sfield[1:]
                reverse = True
            else:
                field = sfield
                reverse = False
            results.sort(
                key=lambda item: getattr(item, field),
                reverse=reverse)
        paginator = self._meta.paginator_class(
            request,
            results,
            resource_uri=self.get_resource_uri(),
            limit=self._meta.limit,
            max_limit=self._meta.max_limit,
            collection_name=self._meta.collection_name,
        )
        to_be_serialized = paginator.page()
        # Dehydrate the bundles in preparation for serialization.
        bundles = []

        for obj in to_be_serialized[self._meta.collection_name]:
            bundle = self.build_bundle(obj=obj, request=request)
            bundles.append(self.full_dehydrate(bundle))

        length = len(bundles)
        to_be_serialized[self._meta.collection_name] = bundles
        to_be_serialized = self.alter_list_data_to_serialize(
            request,
            to_be_serialized
        )
        response = self.create_response(request, to_be_serialized)
        response['Content-Range'] = 'items %d-%d/%d' % (
            paginator.offset,
            paginator.offset+length-1,
            len(results)
        )
        return response

    def dehydrate(self, bundle):
        if self.is_webclient(bundle.request):
            bundle.data['_install_url'] = reverse(
                'plugins_install_available',
                kwargs={'oid': bundle.obj.id},
            )
        return bundle
