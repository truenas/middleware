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
from collections import OrderedDict
import json
import logging
import os
import re
import signal
import subprocess

from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.common import humanize_size
from freenasUI.common.system import is_mounted
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware import zfs
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.system.models import Advanced
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.services.models import iSCSITargetExtent
from freenasUI.storage import forms, models

log = logging.getLogger('storage.views')


#FIXME: Move to a utils module
def _diskcmp(a, b):
    rega = re.search(r'^([a-z/]+)(\d+)$', a[1])
    regb = re.search(r'^([a-z/]+)(\d+)$', b[1])
    if not(rega and regb):
        return 0
    return cmp(
        (a[0], rega.group(1), int(rega.group(2))),
        (b[0], regb.group(1), int(regb.group(2))),
    )


def home(request):
    return render(request, 'storage/index.html', {
        'focused_tab': request.GET.get("tab", None),
    })


def tasks(request):
    task_list = models.Task.objects.order_by("task_filesystem").all()
    return render(request, 'storage/tasks.html', {
        'task_list': task_list,
    })


def replications(request):
    zfsrepl_list = models.Replication.objects.select_related().all()
    return render(request, 'storage/replications.html', {
        'zfsrepl_list': zfsrepl_list,
        'model': models.Replication,
    })


def replications_public_key(request):
    if (os.path.exists('/data/ssh/replication.pub') and
            os.path.isfile('/data/ssh/replication.pub')):
        with open('/data/ssh/replication.pub', 'r') as f:
            key = f.read()
    else:
        key = None
    return render(request, 'storage/replications_key.html', {
        'key': key,
    })


def replications_keyscan(request):

    host = request.POST.get("host")
    port = request.POST.get("port")
    if not host:
        data = {'error': True, 'errmsg': _('Please enter a hostname')}
    else:
        proc = subprocess.Popen([
            "/usr/bin/ssh-keyscan",
            "-p", str(port),
            "-T", "2",
            str(host),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        key, errmsg = proc.communicate()
        if proc.returncode == 0 and key:
            data = {'error': False, 'key': key}
        else:
            if not errmsg:
                errmsg = _("Key could not be retrieved for unknown reason")
            data = {'error': True, 'errmsg': errmsg}

    return HttpResponse(simplejson.dumps(data))


def snapshots(request):
    return render(request, 'storage/snapshots.html')


def volumemanager(request):

    if request.method == "POST":
        form = forms.VolumeManagerForm(request.POST)
        if form.is_valid() and form.save():
            return JsonResp(request, message=_("Volume successfully added."))
        else:
            return JsonResp(request, form=form, formsets={'layout': form._formset})
    disks = []

    # Grab disk list
    # Root device already ruled out
    for disk, info in notifier().get_disks().items():
        disks.append(forms.Disk(
            info['devname'],
            info['capacity'],
            serial=info.get('ident')
        ))
    disks = sorted(disks, key=lambda x: (x.size, x.dev), cmp=_diskcmp)

    # Exclude what's already added
    used_disks = []
    for v in models.Volume.objects.all():
        used_disks.extend(v.get_disks())

    qs = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk')
    used_disks.extend([i.get_device()[5:] for i in qs])

    bysize = dict()
    for d in list(disks):
        if d.dev in used_disks:
            continue
        hsize = forms.humanize_number_si(d.size)
        if hsize not in bysize:
            bysize[hsize] = []
        bysize[hsize].append({
            'dev': d.dev,
            'name': str(d),
            'size': d.size,
            'serial': d.serial,
        })

    bysize = OrderedDict(sorted(bysize.iteritems(), reverse=True))

    qs = models.Volume.objects.filter(vol_fstype='ZFS')
    swap = Advanced.objects.latest('id').adv_swapondrive

    return render(request, "storage/volumemanager.html", {
        'disks': json.dumps(bysize),
        'dedup_warning': forms.DEDUP_WARNING,
        'swap_size': swap * 1024 * 1024 * 1024,
        'extend': json.dumps(
            [{'value': '', 'label': '-----'}] +
            [{
                'label': x.vol_name,
                'value': x.vol_name,
                'enc': x.vol_encrypt > 0
            } for x in qs]
        ),
    })


def volumemanager_ufs(request):

    if request.method == "POST":

        form = forms.VolumeManagerUFSForm(request.POST)
        if form.is_valid():
            form.done(request)
            return JsonResp(request, message=_("Volume successfully added."))
        else:
            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
            zpoolfields = re.compile(r'zpool_(.+)')
            zfsextra = [
                (zpoolfields.search(i).group(1), i, request.POST.get(i))
                for i in request.POST.keys() if zpoolfields.match(i)]

    else:
        form = forms.VolumeManagerUFSForm()
        disks = []
        zfsextra = None
    return render(request, 'storage/wizard.html', {
        'form': form,
        'disks': disks,
        'zfsextra': zfsextra,
        'dedup_warning': forms.DEDUP_WARNING,
    })


def volumemanager_progress(request):
    from freenasUI.middleware import encryption
    if encryption.PROGRESS > 0:
        return HttpResponse(
            'new Object({state: "uploading", received: %s, size: 100});' % (
                int(encryption.PROGRESS),
            ))
    else:
        return HttpResponse('new Object({state: "starting"})')


def volimport(request):

    if request.method == "POST":

        form = forms.VolumeImportForm(request.POST)
        if form.is_valid():
            form.done(request)
            return JsonResp(request, message=_("Volume successfully added."))
        else:

            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
    else:
        form = forms.VolumeImportForm()
        disks = []
    return render(request, 'storage/import.html', {
        'form': form,
        'disks': disks
    })


def dataset_create(request, fs):
    defaults = {'dataset_compression': 'inherit', 'dataset_atime': 'inherit'}
    if request.method == 'POST':
        dataset_form = forms.ZFSDataset_CreateForm(request.POST, fs=fs)
        if dataset_form.is_valid():
            props = {}
            cleaned_data = dataset_form.cleaned_data
            dataset_name = "%s/%s" % (fs, cleaned_data.get('dataset_name'))
            dataset_compression = cleaned_data.get('dataset_compression')
            props['compression'] = dataset_compression.__str__()
            dataset_atime = cleaned_data.get('dataset_atime')
            props['atime'] = dataset_atime.__str__()
            refquota = cleaned_data.get('dataset_refquota')
            if refquota != '0':
                props['refquota'] = refquota.__str__()
            quota = cleaned_data.get('dataset_quota')
            if quota != '0':
                props['quota'] = quota.__str__()
            refreservation = cleaned_data.get('dataset_refreserv')
            if refreservation != '0':
                props['refreservation'] = refreservation.__str__()
            refreservation = cleaned_data.get('dataset_reserv')
            if refreservation != '0':
                props['refreservation'] = refreservation.__str__()
            dedup = cleaned_data.get('dataset_dedup')
            if dedup != 'off':
                props['dedup'] = dedup.__str__()
            recordsize = cleaned_data.get('dataset_recordsize')
            if recordsize:
                props['recordsize'] = recordsize
            errno, errmsg = notifier().create_zfs_dataset(
                path=str(dataset_name),
                props=props)
            if errno == 0:
                return JsonResp(
                    request,
                    message=_("Dataset successfully added."))
            else:
                dataset_form.set_error(errmsg)
                return JsonResp(request, form=dataset_form)
        else:
            return JsonResp(request, form=dataset_form)
    else:
        dataset_form = forms.ZFSDataset_CreateForm(initial=defaults, fs=fs)
    return render(request, 'storage/datasets.html', {
        'form': dataset_form,
        'fs': fs,
    })


def dataset_edit(request, dataset_name):
    if request.method == 'POST':
        dataset_form = forms.ZFSDataset_EditForm(request.POST, fs=dataset_name)
        if dataset_form.is_valid():
            if dataset_form.cleaned_data["dataset_quota"] == "0":
                dataset_form.cleaned_data["dataset_quota"] = "none"
            if dataset_form.cleaned_data["dataset_refquota"] == "0":
                dataset_form.cleaned_data["dataset_refquota"] = "none"

            error = False
            errors = {}

            for attr in (
                'compression',
                'atime',
                'dedup',
                'reservation',
                'refreservation',
                'quota',
                'refquota',
            ):
                formfield = 'dataset_%s' % attr
                if dataset_form.cleaned_data[formfield] == "inherit":
                    success, err = notifier().zfs_inherit_option(
                        dataset_name,
                        attr)
                else:
                    success, err = notifier().zfs_set_option(
                        dataset_name,
                        attr,
                        dataset_form.cleaned_data[formfield])
                error |= not success
                if not success:
                    errors[formfield] = err

            if not error:
                return JsonResp(
                    request,
                    message=_("Dataset successfully edited."))
            else:
                for field, err in errors.items():
                    dataset_form._errors[field] = dataset_form.error_class([
                        err,
                    ])
                return JsonResp(request, form=dataset_form)
        else:
            return JsonResp(request, form=dataset_form)
    else:
        dataset_form = forms.ZFSDataset_EditForm(fs=dataset_name)
    return render(request, 'storage/dataset_edit.html', {
        'dataset_name': dataset_name,
        'form': dataset_form
    })


def zvol_create(request, parent):
    defaults = {'zvol_compression': 'inherit', }
    if request.method == 'POST':
        zvol_form = forms.ZVol_CreateForm(request.POST, vol_name=parent)
        if zvol_form.is_valid():
            props = {}
            cleaned_data = zvol_form.cleaned_data
            zvol_size = cleaned_data.get('zvol_size')
            zvol_blocksize = cleaned_data.get("zvol_blocksize")
            zvol_name = "%s/%s" % (parent, cleaned_data.get('zvol_name'))
            zvol_compression = cleaned_data.get('zvol_compression')
            props['compression'] = str(zvol_compression)
            if zvol_blocksize:
                props['volblocksize'] = zvol_blocksize
            errno, errmsg = notifier().create_zfs_vol(
                name=str(zvol_name),
                size=str(zvol_size),
                sparse=cleaned_data.get("zvol_sparse", False),
                props=props)
            if errno == 0:
                return JsonResp(
                    request,
                    message=_("ZFS Volume successfully added."))
            else:
                zvol_form.set_error(errmsg)
    else:
        zvol_form = forms.ZVol_CreateForm(
            initial=defaults,
            vol_name=parent)
    return render(request, 'storage/zvols.html', {
        'form': zvol_form,
        'volume_name': parent,
    })


def zvol_delete(request, name):

    if request.method == 'POST':
        extents = iSCSITargetExtent.objects.filter(
            iscsi_target_extent_type='ZVOL',
            iscsi_target_extent_path='zvol/' + name)
        if extents.count() > 0:
            return JsonResp(
                request,
                error=True,
                message=_(
                    "This is in use by the iscsi target, please remove "
                    "it there first."))
        retval = notifier().destroy_zfs_vol(name)
        if retval == '':
            return JsonResp(
                request,
                message=_("ZFS Volume successfully destroyed."))
        else:
            return JsonResp(request, error=True, message=retval)
    else:
        return render(request, 'storage/zvol_confirm_delete.html', {
            'name': name,
        })


def zfsvolume_edit(request, object_id):

    mp = models.MountPoint.objects.get(pk=object_id)
    volume_form = forms.ZFSVolume_EditForm(mp=mp)

    if request.method == 'POST':
        volume_form = forms.ZFSVolume_EditForm(request.POST, mp=mp)
        if volume_form.is_valid():
            volume = mp.mp_volume
            volume_name = volume.vol_name
            volume_name = mp.mp_path.replace("/mnt/", "")

            if volume_form.cleaned_data["volume_refquota"] == "0":
                volume_form.cleaned_data["volume_refquota"] = "none"

            error, errors = False, {}
            for attr in (
                'compression',
                'atime',
                'dedup',
                'refquota',
                'refreservation',
            ):
                formfield = 'volume_%s' % attr
                if volume_form.cleaned_data[formfield] == "inherit":
                    success, err = notifier().zfs_inherit_option(
                        volume_name,
                        attr)
                else:
                    success, err = notifier().zfs_set_option(
                        volume_name,
                        attr,
                        volume_form.cleaned_data[formfield])
                if not success:
                    error = True
                    errors[formfield] = err

            if not error:
                return JsonResp(
                    request,
                    message=_("Native dataset successfully edited."))
            else:
                for field, err in errors.items():
                    volume_form._errors[field] = volume_form.error_class([
                        err,
                    ])
    return render(request, 'storage/volume_edit.html', {
        'mp': mp,
        'form': volume_form
    })


def mp_permission(request, path):
    if request.method == 'POST':
        form = forms.MountPointAccessForm(request.POST)
        if form.is_valid():
            form.commit(path=path)
            return JsonResp(
                request,
                message=_("Mount Point permissions successfully updated."))
    else:
        form = forms.MountPointAccessForm(initial={'path': path})
    return render(request, 'storage/permission.html', {
        'path': path,
        'form': form,
    })


def dataset_delete(request, name):

    datasets = zfs.list_datasets(path=name, recursive=True)
    if request.method == 'POST':
        form = forms.Dataset_Destroy(request.POST, fs=name, datasets=datasets)
        if form.is_valid():
            retval = notifier().destroy_zfs_dataset(path=name, recursive=True)
            if retval == '':
                notifier().restart("collectd")
                return JsonResp(
                    request,
                    message=_("Dataset successfully destroyed."))
            else:
                return JsonResp(request, error=True, message=retval)
    else:
        form = forms.Dataset_Destroy(fs=name, datasets=datasets)
    return render(request, 'storage/dataset_confirm_delete.html', {
        'name': name,
        'form': form,
        'datasets': datasets,
    })


def snapshot_delete(request, dataset, snapname):
    snapshot = '%s@%s' % (dataset, snapname)
    if request.method == 'POST':
        retval = notifier().destroy_zfs_dataset(path=str(snapshot))
        if retval == '':
            notifier().restart("collectd")
            return JsonResp(
                request,
                message=_("Snapshot successfully deleted."))
        else:
            return JsonResp(request, error=True, message=retval)
    else:
        return render(request, 'storage/snapshot_confirm_delete.html', {
            'snapname': snapname,
            'dataset': dataset,
        })


def snapshot_delete_bulk(request):

    snaps = request.POST.get("snaps", None)
    delete = request.POST.get("delete", None)
    if snaps and delete == "true":
        snap_list = snaps.split('|')
        for snapshot in snap_list:
            retval = notifier().destroy_zfs_dataset(path=str(snapshot))
            if retval != '':
                return JsonResp(request, error=True, message=retval)
        notifier().restart("collectd")
        return JsonResp(request, message=_("Snapshots successfully deleted."))

    return render(request, 'storage/snapshot_confirm_delete_bulk.html', {
        'snaps': snaps,
    })


def snapshot_rollback(request, dataset, snapname):
    snapshot = '%s@%s' % (dataset, snapname)
    if request.method == "POST":
        ret = notifier().rollback_zfs_snapshot(snapshot=snapshot.__str__())
        if ret == '':
            return JsonResp(request, message=_("Rollback successful."))
        else:
            return JsonResp(request, error=True, message=ret)
    else:
        return render(request, 'storage/snapshot_confirm_rollback.html', {
            'snapname': snapname,
            'dataset': dataset,
        })


def manualsnap(request, fs):
    if request.method == "POST":
        form = forms.ManualSnapshotForm(request.POST)
        if form.is_valid():
            form.commit(fs)
            return JsonResp(request, message=_("Snapshot successfully taken."))
    else:
        form = forms.ManualSnapshotForm()
    return render(request, 'storage/manualsnap.html', {
        'form': form,
        'fs': fs,
    })


def clonesnap(request, snapshot):
    initial = {'cs_snapshot': snapshot}
    if request.method == "POST":
        form = forms.CloneSnapshotForm(request.POST, initial=initial)
        if form.is_valid():
            retval = form.commit()
            if retval == '':
                return JsonResp(
                    request,
                    message=_("Snapshot successfully cloned."))
            else:
                return JsonResp(request, error=True, message=retval)
    else:
        is_volume = 'volume' in request.GET
        form = forms.CloneSnapshotForm(initial=initial, is_volume=is_volume)
    return render(request, 'storage/clonesnap.html', {
        'form': form,
        'snapshot': snapshot,
    })


def geom_disk_replace(request, vname):

    volume = models.Volume.objects.get(vol_name=vname)
    if request.method == "POST":
        form = forms.UFSDiskReplacementForm(request.POST)
        if form.is_valid():
            if form.done(volume):
                return JsonResp(
                    request,
                    message=_("Disk replacement has been initiated."))
            else:
                return JsonResp(
                    request,
                    error=True,
                    message=_("An error occurred."))

    else:
        form = forms.UFSDiskReplacementForm()
    return render(request, 'storage/geom_disk_replace.html', {
        'form': form,
        'vname': vname,
    })


def disk_detach(request, vname, label):

    volume = models.Volume.objects.get(vol_name=vname)

    if request.method == "POST":
        notifier().zfs_detach_disk(volume, label)
        return JsonResp(
            request,
            message=_("Disk detach has been successfully done."))

    return render(request, 'storage/disk_detach.html', {
        'vname': vname,
        'label': label,
    })


def disk_offline(request, vname, label):

    volume = models.Volume.objects.get(vol_name=vname)
    disk = notifier().label_to_disk(label)

    if request.method == "POST":
        notifier().zfs_offline_disk(volume, label)
        return JsonResp(
            request,
            message=_("Disk offline operation has been issued."))

    return render(request, 'storage/disk_offline.html', {
        'vname': vname,
        'label': label,
        'disk': disk,
    })


def zpool_disk_remove(request, vname, label):

    volume = models.Volume.objects.get(vol_name=vname)
    disk = notifier().label_to_disk(label)

    if request.method == "POST":
        notifier().zfs_remove_disk(volume, label)
        return JsonResp(request, message=_("Disk has been removed."))

    return render(request, 'storage/disk_remove.html', {
        'vname': vname,
        'label': label,
        'disk': disk,
    })


def volume_detach(request, vid):

    volume = models.Volume.objects.get(pk=vid)
    usedbytes = sum(
        [mp._get_used_bytes() for mp in volume.mountpoint_set.all()]
    )
    usedsize = humanize_size(usedbytes)
    services = volume.has_attachments()
    if volume.vol_encrypt > 0:
        request.session["allow_gelikey"] = True
    if request.method == "POST":
        form = forms.VolumeExport(
            request.POST,
            instance=volume,
            services=services)
        if form.is_valid():
            try:
                volume.delete(
                    destroy=form.cleaned_data['mark_new'],
                    cascade=form.cleaned_data.get('cascade', True))
                return JsonResp(
                    request,
                    message=_("The volume has been successfully detached"))
            except ServiceFailed, e:
                return JsonResp(request, error=True, message=unicode(e))
    else:
        form = forms.VolumeExport(instance=volume, services=services)
    return render(request, 'storage/volume_detach.html', {
        'volume': volume,
        'form': form,
        'used': usedsize,
        'services': services,
    })


def zpool_scrub(request, vid):
    volume = models.Volume.objects.get(pk=vid)
    try:
        pool = notifier().zpool_parse(volume.vol_name)
    except:
        raise MiddlewareError(
            _('Pool output could not be parsed. Is the pool imported?')
        )
    if request.method == "POST":
        if request.POST.get("scrub") == 'IN_PROGRESS':
            notifier().zfs_scrub(str(volume.vol_name), stop=True)
        else:
            notifier().zfs_scrub(str(volume.vol_name))
        return JsonResp(request, message=_("The scrub process has begun"))

    return render(request, 'storage/scrub_confirm.html', {
        'volume': volume,
        'scrub': pool.scrub,
    })


def zpool_disk_replace(request, vname, label):

    disk = notifier().label_to_disk(label)
    if disk is None:
        disk = label
    volume = models.Volume.objects.get(vol_name=vname)
    if request.method == "POST":
        form = forms.ZFSDiskReplacementForm(
            request.POST,
            volume=volume,
            disk=disk
        )
        if form.is_valid():
            if form.done(disk, label):
                return JsonResp(
                    request,
                    message=_("Disk replacement has been initiated."))
            else:
                return JsonResp(
                    request,
                    error=True,
                    message=_("An error occurred."))

    else:
        form = forms.ZFSDiskReplacementForm(volume=volume, disk=disk)
    return render(request, 'storage/zpool_disk_replace.html', {
        'form': form,
        'vname': vname,
        'encrypted': volume.vol_encrypt > 0,
        'label': label,
        'disk': disk,
    })


def multipath_status(request):
    return render(request, 'storage/multipath_status.html')


def multipath_status_json(request):

    multipaths = notifier().multipath_all()
    _id = 1
    items = []
    for mp in multipaths:
        children = []
        for cn in mp.consumers:
            actions = {}
            items.append({
                'id': str(_id),
                'name': cn.devname,
                'status': cn.status,
                'type': 'consumer',
                'actions': simplejson.dumps(actions),
            })
            children.append({'_reference': str(_id)})
            _id += 1
        data = {
            'id': str(_id),
            'name': mp.devname,
            'status': mp.status,
            'type': 'root',
            'children': children,
        }
        items.append(data)
        _id += 1
    return HttpResponse(simplejson.dumps({
        'identifier': 'id',
        'label': 'name',
        'items': items,
    }, indent=2), content_type='application/json')


def disk_wipe(request, devname):

    form = forms.DiskWipeForm()
    if request.method == "POST":
        form = forms.DiskWipeForm(request.POST)
        if form.is_valid():
            mounted = []
            for geom in notifier().disk_get_consumers(devname):
                gname = geom.xpathEval("./name")[0].content
                dev = "/dev/%s" % (gname, )
                if dev not in mounted and is_mounted(device=dev):
                    mounted.append(dev)
            for vol in models.Volume.objects.filter(
                vol_fstype='ZFS'
            ):
                if devname in vol.get_disks():
                    mounted.append(vol.vol_name)
            if mounted:
                form._errors['__all__'] = form.error_class([
                    "Umount the following mount points before proceeding:"
                    "<br /> %s" % (
                    '<br /> '.join(mounted),
                    )
                ])
            else:
                notifier().disk_wipe(devname, form.cleaned_data['method'])
                return JsonResp(
                    request,
                    message=_("Disk successfully wiped"))

        return JsonResp(request, form=form)

    return render(request, "storage/disk_wipe.html", {
        'devname': devname,
        'form': form,
    })


def disk_wipe_progress(request, devname):

    pidfile = '/var/tmp/disk_wipe_%s.pid' % (devname, )
    if not os.path.exists(pidfile):
        return HttpResponse('new Object({state: "starting"});')

    with open(pidfile, 'r') as f:
        pid = f.read()

    try:
        os.kill(int(pid), signal.SIGINFO)
        with open('/var/tmp/disk_wipe_%s.progress' % (devname, ), 'r') as f:
            data = f.read()
            transf = re.findall(
                r'^(?P<bytes>\d+) bytes transferred.*',
                data,
                re.M)
            if transf:
                pipe = subprocess.Popen([
                    "/usr/sbin/diskinfo",
                    devname,
                ], stdout=subprocess.PIPE)
                output = pipe.communicate()[0]
                size = output.split()[2]
                received = transf[-1]
        return HttpResponse(
            'new Object({state: "uploading", received: %s, size: %s});' % (
                received,
                size))

    except Exception, e:
        log.warn("Could not check for disk wipe progress: %s", e)
    return HttpResponse('new Object({state: "starting"});')


def volume_create_passphrase(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if request.method == "POST":
        form = forms.CreatePassphraseForm(request.POST)
        if form.is_valid():
            form.done(volume=volume)
            return JsonResp(
                request,
                message=_("Passphrase created"))
    else:
        form = forms.CreatePassphraseForm()
    return render(request, "storage/create_passphrase.html", {
        'volume': volume,
        'form': form,
    })


def volume_change_passphrase(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if request.method == "POST":
        form = forms.ChangePassphraseForm(request.POST)
        if form.is_valid():
            form.done(volume=volume)
            return JsonResp(
                request,
                message=_("Passphrase updated"))
    else:
        form = forms.ChangePassphraseForm()
    return render(request, "storage/change_passphrase.html", {
        'volume': volume,
        'form': form,
    })


def volume_unlock(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if volume.vol_encrypt < 2:
        if request.method == "POST":
            notifier().start("geli")
            zimport = notifier().zfs_import(
                volume.vol_name,
                id=volume.vol_guid
            )
            if zimport and volume.is_decrypted:
                notifier().sync_encrypted(volume=volume)
                return JsonResp(
                    request,
                    message=_("Volume unlocked"))
            else:
                return JsonResp(
                    request,
                    message=_("Volume failed unlocked"))
        return render(request, "storage/unlock.html")

    if request.method == "POST":
        form = forms.UnlockPassphraseForm(request.POST, request.FILES)
        if form.is_valid():
            form.done(volume=volume)
            return JsonResp(
                request,
                message=_("Volume unlocked"))
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.UnlockPassphraseForm()
    return render(request, "storage/unlock_passphrase.html", {
        'volume': volume,
        'form': form,
    })


def volume_key(request, object_id):

    if request.method == "POST":
        form = forms.KeyForm(request.POST)
        if form.is_valid():
            request.session["allow_gelikey"] = True
            return JsonResp(
                request,
                message=_("GELI key download starting..."),
                events=["window.location='%s';" % (
                    reverse("storage_volume_key_download",
                        kwargs={'object_id': object_id}),
                )],
            )
    else:
        form = forms.KeyForm()

    return render(request, "storage/key.html", {
        'form': form,
    })


def volume_key_download(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if "allow_gelikey" not in request.session:
        return HttpResponseRedirect('/')

    geli_keyfile = volume.get_geli_keyfile()
    wrapper = FileWrapper(file(geli_keyfile))

    response = HttpResponse(wrapper, content_type='application/octet-stream')
    response['Content-Length'] = os.path.getsize(geli_keyfile)
    response['Content-Disposition'] = 'attachment; filename=geli.key'
    del request.session["allow_gelikey"]
    return response


def volume_rekey(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if request.method == "POST":
        form = forms.ReKeyForm(request.POST, volume=volume)
        if form.is_valid():
            form.done()
            return JsonResp(
                request,
                message=_("Encryption re-key succeeded"))
    else:
        form = forms.ReKeyForm(volume=volume)

    return render(request, "storage/rekey.html", {
        'form': form,
    })


def volume_recoverykey_add(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if request.method == "POST":
        form = forms.KeyForm(request.POST)
        if form.is_valid():
            reckey = notifier().geli_recoverykey_add(volume)
            request.session["allow_gelireckey"] = reckey
            return JsonResp(
                request,
                message=_("GELI recovery key download starting..."),
                events=["window.location='%s';" % (
                    reverse("storage_volume_recoverykey_download",
                        kwargs={'object_id': object_id}),
                )],
            )
    else:
        form = forms.KeyForm()

    return render(request, "storage/recoverykey_add.html", {
        'form': form,
    })


def volume_recoverykey_download(request, object_id):

    if "allow_gelireckey" not in request.session:
        return HttpResponseRedirect('/')

    rec_keyfile = request.session["allow_gelireckey"]
    with open(rec_keyfile, 'rb') as f:

        response = HttpResponse(
            f.read(),
            content_type='application/octet-stream')
    response['Content-Length'] = os.path.getsize(rec_keyfile)
    response['Content-Disposition'] = 'attachment; filename=geli_recovery.key'
    del request.session["allow_gelireckey"]
    os.unlink(rec_keyfile)
    return response


def volume_recoverykey_remove(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if request.method == "POST":
        form = forms.KeyForm(request.POST)
        if form.is_valid():
            notifier().geli_delkey(volume)
            return JsonResp(
                request,
                message=_("Recovery has been removed"))
    else:
        form = forms.KeyForm()

    return render(request, "storage/recoverykey_remove.html", {
        'form': form,
    })


def disk_editbulk(request):

    if request.method == "POST":
        ids = request.POST.get("ids", "").split(",")
        disks = models.Disk.objects.filter(id__in=ids)
        form = forms.DiskEditBulkForm(request.POST, disks=disks)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message=_("Disks successfully edited"))

        return JsonResp(request, form=form)
    else:
        ids = request.GET.get("ids", "").split(",")
        disks = models.Disk.objects.filter(id__in=ids)
        form = forms.DiskEditBulkForm(disks=disks)

    return render(request, "storage/disk_editbulk.html", {
        'form': form,
        'disks': ', '.join([disk.disk_name for disk in disks]),
    })
