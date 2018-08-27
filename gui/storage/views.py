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
from functools import cmp_to_key
import json
import logging
import os
import re
import urllib.request, urllib.parse, urllib.error
from time import sleep

from wsgiref.util import FileWrapper
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _

from freenasUI.common import humanize_size
from freenasUI.common.pipesubr import pipeopen
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client, ClientException
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.util import JobAborted, JobFailed, wait_job
from freenasUI.system.models import Advanced
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.services.models import iSCSITargetExtent
from freenasUI.storage import forms, models

DISK_WIPE_JOB_ID = None
log = logging.getLogger('storage.views')


# FIXME: Move to a utils module
def _diskcmp(a, b):
    rega = re.search(r'^([a-z/]+)(\d+)$', a.dev)
    regb = re.search(r'^([a-z/]+)(\d+)$', b.dev)
    if not(rega and regb):
        return 0
    la = (a.size, rega.group(1), int(rega.group(2)))
    lb = (b.size, regb.group(1), int(regb.group(2)))
    return (la > lb) - (la < lb)


def home(request):

    view = appPool.hook_app_index('storage', request)
    view = [_f for _f in view if _f]
    if view:
        return view[0]

    try:
        resilver = models.Resilver.objects.order_by('-id')[0]
    except Exception:
        resilver = models.Resilver.objects.create()

    tabs = appPool.hook_app_tabs('storage', request)
    return render(request, 'storage/index.html', {
        'focused_tab': request.GET.get("tab", 'storage.Volumes.View'),
        'hook_tabs': tabs,
        'resilver_edit_url': f'{resilver.get_edit_url()}?inline=true'
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
    with client as c:
        key = c.call('replication.public_key')
    return render(request, 'storage/replications_key.html', {
        'key': key,
    })


def replications_authtoken(request):
    with client as c:
        tokenid = c.call('auth.generate_token', 120)
    return render(request, 'storage/replications_authtoken.html', {
        'tokenid': tokenid,
    })


def replications_keyscan(request):

    host = request.POST.get("host")
    port = request.POST.get("port")
    if not host:
        data = {'error': True, 'errmsg': _('Please enter a hostname')}
    else:
        with client as c:
            try:
                key = c.call('replication.ssh_keyscan', str(host), int(port))
                data = {'error': False, 'key': key}
            except ClientException as e:
                data = {'error': True, 'errmsg': str(e)}
    return HttpResponse(json.dumps(data))


def snapshots(request):
    return render(request, 'storage/snapshots.html')


def volumemanager(request):

    if request.method == "POST":
        form = forms.VolumeManagerForm(request.POST)
        try:
            if form.is_valid() and form.save():
                events = []
                form.done(request, events)
                return JsonResp(
                    request,
                    message=_("Volume successfully added."),
                    events=events,
                )
            else:
                return JsonResp(request, form=form, formsets={'layout': {
                    'instance': form._formset,
                }})
        except MiddlewareError as e:
            form._errors['__all__'] = form.error_class([str(e)])
            return JsonResp(request, form=form, formsets={'layout': {
                'instance': form._formset,
            }})

    _n = notifier()
    disks = []
    # Grab disk list
    # Root device already ruled out
    for disk, info in list(_n.get_disks().items()):
        disks.append(forms.Disk(
            info['devname'],
            info['capacity'],
            serial=info.get('ident')
        ))
    disks = sorted(disks, key=cmp_to_key(_diskcmp))

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
        display_name = d.dev
        if '/' in display_name:
            display_name = display_name.split('/')[-1]
        bysize[hsize].append({
            'dev': d.dev,
            'name': str(d),
            'displayName': display_name,
            'size': d.size,
            'serial': d.serial,
        })

    bysize = OrderedDict(sorted(iter(bysize.items()), reverse=True))

    swap = Advanced.objects.latest('id').adv_swapondrive

    encwarn = (
        '<span style="color: red; font-size:110%%;">%s</span>'
        '<p>%s</p>'
        '<p>%s</p>'
        '<p>%s</p>'
    ) % (
        _('WARNING!'),
        _(
            'Always backup the key! If the key is lost, the data on the disks '
            'will also be lost with no hope of recovery.'
        ),
        _(
            'This type of encryption is primarily targeted at users who are '
            'storing sensitive data and want the ability to remove disks from '
            'the pool and dispose of/re-use them without concern for erasure.'
        ),
        _(
            'iXsystems, Inc. can not be held responsible for any lost '
            'or unrecoverable data as a consequence of using this feature.'
        ),
    )

    extend = [{'value': '', 'label': '-----'}]
    qs = models.Volume.objects.all()
    for vol in qs:
        if not vol.is_decrypted():
            continue
        try:
            _n.zpool_parse(vol.vol_name)
        except Exception:
            continue
        extend.append({
            'label': vol.vol_name,
            'value': vol.vol_name,
            'enc': vol.vol_encrypt > 0
        })

    return render(request, "storage/volumemanager.html", {
        'disks': json.dumps(bysize),
        'dedup_warning': forms.DEDUP_WARNING,
        'encryption_warning': encwarn,
        'swap_size': swap * 1024 * 1024 * 1024,
        'manual_url': reverse('storage_volumemanager_zfs'),
        'extend': json.dumps(extend),
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


def volumemanager_zfs(request):

    if request.method == "POST":

        form = forms.ZFSVolumeWizardForm(request.POST)
        events = []
        if form.is_valid() and form.done(request, events):
            return JsonResp(
                request,
                message=_("Volume successfully added."),
                events=events,
            )
        else:
            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
            zpoolfields = re.compile(r'zpool_(.+)')
            zfsextra = [
                (zpoolfields.search(i).group(1), i, request.POST.get(i))
                for i in list(request.POST.keys()) if zpoolfields.match(i)
            ]

    else:
        form = forms.ZFSVolumeWizardForm()
        disks = []
        zfsextra = None
    # dedup = forms._dedup_enabled()
    dedup = True
    return render(request, 'storage/zfswizard.html', {
        'form': form,
        'disks': disks,
        'zfsextra': zfsextra,
        'dedup': dedup,
    })


def volimport(request):
    with client as c:
        job = c.call('pool.get_current_import_disk_job')
    if job is not None:
        if job["state"] in ["SUCCESS", "FAILED", "ABORTED"]:
            return render(
                request, 'storage/import_stats.html', job
            )
        return render(request, 'storage/import_progress.html')

    if request.method == "POST":
        form = forms.VolumeImportForm(request.POST)
        if form.is_valid():
            form.done(request)
            with client as c:
                if form.cleaned_data.get('volume_fstype').lower() == 'msdosfs':
                    fs_options = {'locale': form.cleaned_data.get('volume_msdosfs_locale')}
                else:
                    fs_options = {}
                c.call(
                    'pool.import_disk',
                    "/dev/{0}".format(form.cleaned_data.get('volume_disks')),
                    form.cleaned_data.get('volume_fstype').lower(),
                    fs_options,
                    form.cleaned_data.get('volume_dest_path'),
                )
            return render(request, 'storage/import_progress.html')
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


def volimport_progress(request):
    with client as c:
        job = c.call('pool.get_current_import_disk_job')

    return HttpResponse(json.dumps({
        "status": "finished" if job["state"] in ["SUCCESS", "FAILED", "ABORTED"] else job["progress"]["description"],
        "volume": job["arguments"][0],
        "extra": job["progress"]["extra"],
        "percent": job["progress"]["percent"],
    }), content_type='application/json')


def volimport_abort(request):
    if request.method == 'POST':
        with client as c:
            job = c.call('pool.get_current_import_disk_job')

        if job["state"] == "SUCCESS":
            with client as c:
                c.call('pool.dismiss_current_import_disk_job')

            return JsonResp(request, message=_("Volume successfully Imported."))

        if job["state"] == "FAILED":
            with client as c:
                c.call('pool.dismiss_current_import_disk_job')

            return JsonResp(request, message=_("Error Importing Volume"))

        with client as c:
            c.call("core.job_abort", job["id"])

        for i in range(10):
            with client as c:
                job = c.call('pool.get_current_import_disk_job')
                if job["state"] != "RUNNING":
                    break

            sleep(1)
        else:
            return JsonResp(request, message=_("Error aborting Volume Import"))

        with client as c:
            c.call('pool.dismiss_current_import_disk_job')

        return render(
            request,
            'storage/import_stats.html',
            job,
        )


def dataset_create(request, fs):
    if request.method == 'POST':
        form = forms.ZFSDatasetCreateForm(request.POST, fs=fs)
        if form.is_valid():
            if form.save():
                return JsonResp(request,
                                message=_("ZFS Volume successfully added."))
        else:
            return JsonResp(request, form=form)
    else:
        defaults = {'dataset_atime': 'inherit',
                    'dataset_sync': 'inherit',
                    'dataset_compression': 'inherit'}
        form = forms.ZFSDatasetCreateForm(initial=defaults, fs=fs)
    return render(request, 'storage/datasets.html', {
        'form': form,
        'fs': fs,
    })


def dataset_edit(request, dataset_name):
    if request.method == 'POST':
        form = forms.ZFSDatasetEditForm(request.POST, fs=dataset_name)
        if form.is_valid() and form.save():
            return JsonResp(request, message=_("Dataset successfully edited."))
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.ZFSDatasetEditForm(fs=dataset_name)
    return render(request, 'storage/dataset_edit.html', {
        'dataset_name': dataset_name,
        'form': form
    })


def promote_zfs(request, name):
    try:
        with client as c:
            c.call("zfs.dataset.promote", name)
            return HttpResponse(_("Filesystem successfully promoted."))
    except ClientException:
        return HttpResponse(_("Filesystem is not a clone or has already been promoted."))


def zvol_create(request, parent):
    if request.method == 'POST':
        zvol_form = forms.ZVol_CreateForm(request.POST, parentds=parent)
        if zvol_form.is_valid():
            if zvol_form.save():
                return JsonResp(
                    request,
                    message=_("ZFS Volume successfully added."))
    else:
        zvol_form = forms.ZVol_CreateForm(
            initial={'zvol_sync': 'inherit',
                     'zvol_compression': 'inherit'},
            parentds=parent)
    return render(request, 'storage/zvols.html', {
        'form': zvol_form,
        'volume_name': parent,
    })


def zvol_delete(request, name):

    if request.method == 'POST':
        form = forms.ZvolDestroyForm(request.POST, fs=name)
        if form.is_valid():
            with client as c:
                try:
                    c.call('pool.dataset.delete', name)
                except ClientException as e:
                    return JsonResp(
                        request,
                        error=True,
                        message=e.error)

            return JsonResp(
                request,
                message=_("ZFS Volume successfully destroyed."))
    else:
        form = forms.ZvolDestroyForm(fs=name)
    return render(request, 'storage/zvol_confirm_delete.html', {
        'form': form,
        'name': name,
    })


def zvol_edit(request, name):
    if request.method == 'POST':
        form = forms.ZVol_EditForm(request.POST, name=name)
        if form.is_valid() and form.save():
            return JsonResp(request, message=_("Zvol successfully edited."))
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.ZVol_EditForm(name=name)
    return render(request, 'storage/volume_edit.html', {
        'form': form,
    })


def mp_permission(request, path):
    path = urllib.parse.unquote_plus(path)
    # FIXME: dojo cannot handle urls partially urlencoded %2F => /
    if not path.startswith('/'):
        path = '/' + path
    if request.method == 'POST':
        form = forms.MountPointAccessForm(request.POST)
        if form.is_valid():
            if form.commit(path):
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
    with client as c:
        datasets = c.call("pool.dataset.query", [["name", "=", name]], {"get": True})["children"]
    if request.method == 'POST':
        form = forms.Dataset_Destroy(request.POST, fs=name, datasets=datasets)
        if form.is_valid():
            with client as c:
                try:
                    c.call("pool.dataset.delete", name, True)
                    return JsonResp(
                        request,
                        message=_("Dataset successfully destroyed."))
                except ClientException as e:
                    return JsonResp(request, error=True, message=e.error)
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
        form = forms.ManualSnapshotForm(request.POST, fs=fs)
        if form.is_valid():
            form.commit(fs)
            return JsonResp(request, message=_("Snapshot successfully taken."))
    else:
        form = forms.ManualSnapshotForm(fs=fs)
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


def disk_online(request, vname, label):

    volume = models.Volume.objects.get(vol_name=vname)
    disk = notifier().label_to_disk(label)

    if request.method == "POST":
        notifier().zfs_online_disk(volume, label)
        return JsonResp(
            request,
            message=_("Disk online operation has been issued."))

    return render(request, 'storage/disk_online.html', {
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

    _n = notifier()
    standby_offline = False
    if not _n.is_freenas() and _n.failover_licensed():
        try:
            with client as c:
                c.call('failover.call_remote', 'core.ping')
        except Exception:
            standby_offline = True

    volume = models.Volume.objects.get(pk=vid)
    usedbytes = volume._get_used_bytes()
    usedsize = humanize_size(usedbytes) if usedbytes else None
    with client as c:
        services = {
            key: val
            for key, val in list(c.call('pool.attachments', volume.id).items()) if len(val) > 0
        }
    if volume.vol_encrypt > 0:
        request.session["allow_gelikey"] = True
    if request.method == "POST":
        form = forms.VolumeExport(
            request.POST,
            instance=volume,
            services=services)
        if form.is_valid():
            _n = notifier()
            if '__confirm' not in request.POST and not _n.is_freenas() and _n.failover_licensed():
                remaining_volumes = models.Volume.objects.exclude(pk=vid)
                if not remaining_volumes.exists():
                    message = render_to_string('freeadmin/generic_model_confirm.html', {
                        'message': 'Warning: this pool is required for HA to function.<br />Do you want to continue?',
                    })
                    return JsonResp(request, confirm=message)
            try:
                events = []
                form.done(request, events)
                return JsonResp(
                    request,
                    message=_("The volume has been successfully detached"),
                    events=events,
                )
            except ServiceFailed as e:
                return JsonResp(
                    request,
                    form=form,
                    error=True,
                    message=e.value,
                    events=["serviceFailed(\"%s\")" % e.service])
    else:
        form = forms.VolumeExport(instance=volume, services=services)
    return render(request, 'storage/volume_detach.html', {
        'standby_offline': standby_offline,
        'volume': volume,
        'form': form,
        'used': usedsize,
        'services': services,
    })


def zpool_scrub(request, vid):
    volume = models.Volume.objects.get(pk=vid)
    try:
        pool = notifier().zpool_parse(volume.vol_name)
    except Exception:
        raise MiddlewareError(
            _('Pool output could not be parsed. Is the pool imported?')
        )
    if request.method == "POST":
        with client as c:
            if request.POST["action"] == "start":
                c.call('pool.scrub', vid, 'START')
                return JsonResp(request, message=_("The scrub process has been started"))
            elif request.POST["action"] == "stop":
                c.call('pool.scrub', vid, 'STOP')
                return JsonResp(request, message=_("The scrub process has been stopped"))
            elif request.POST["action"] == "pause":
                c.call('pool.scrub', vid, 'PAUSE')
                return JsonResp(request, message=_("The scrub process has been paused"))

    return render(request, 'storage/scrub_confirm.html', {
        'volume': volume,
        'scrub': pool.scrub,
    })


def zpool_disk_replace(request, vname, label):

    volume = models.Volume.objects.get(vol_name=vname)
    if request.method == "POST":
        form = forms.ZFSDiskReplacementForm(
            request.POST,
            volume=volume,
            label=label,
        )
        if form.is_valid() and form.done():
            return JsonResp(
                request,
                message=_("Disk replacement has been initiated."))
        return JsonResp(request, form=form)
    else:
        form = forms.ZFSDiskReplacementForm(volume=volume, label=label)
    return render(request, 'storage/zpool_disk_replace.html', {
        'form': form,
        'vname': vname,
        'encrypted': volume.vol_encrypt > 0,
        'label': label,
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
                'lunid': cn.lunid,
                'type': 'consumer',
                'actions': json.dumps(actions),
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
    return HttpResponse(json.dumps({
        'identifier': 'id',
        'label': 'name',
        'items': items,
    }, indent=2), content_type='application/json')


def disk_wipe(request, devname):
    global DISK_WIPE_JOB_ID

    if request.method == "POST":
        form = forms.DiskWipeForm(request.POST, disk=devname)
        if form.is_valid():
            DISK_WIPE_JOB_ID = None
            try:
                with client as c:
                    DISK_WIPE_JOB_ID = c.call('disk.wipe', devname, form.cleaned_data['method'])
                    wait_job(c, DISK_WIPE_JOB_ID)
            except JobAborted:
                raise MiddlewareError(_('Disk wipe job was aborted'))
            except JobFailed as e:
                raise MiddlewareError(_('Disk wipe job failed: %s') % str(e.value))
            return JsonResp(
                request,
                message=_("Disk successfully wiped"))

        return JsonResp(request, form=form)

    form = forms.DiskWipeForm(disk=devname)

    return render(request, "storage/disk_wipe.html", {
        'devname': devname,
        'form': form,
    })


def disk_wipe_progress(request, devname):
    global DISK_WIPE_JOB_ID
    details = 'Starting Disk Wipe'
    indeterminate = True
    progress = 0
    step = 1
    finished = False
    error = False
    if not DISK_WIPE_JOB_ID:
        return HttpResponse('new Object({state: "starting"});')

    with client as c:
        job = c.call('core.get_jobs', [['id', '=', DISK_WIPE_JOB_ID]])

    if not job:
        return HttpResponse('new Object({state: "starting"});')
    job = job[0]

    if job['state'] == 'FAILED':
        error = True
        details = job['error']
    elif job['state'] == 'RUNNING':
        progress = job['progress']['percent'] or 0
    elif job['state'] == 'SUCCESS':
        finished = True

    data = {
        'error': error,
        'finished': finished,
        'indeterminate': indeterminate,
        'percent': progress,
        'step': step,
        'mode': "single",
        'details': details
    }
    return HttpResponse(
        json.dumps(data),
        content_type='application/json',
    )


def volume_create_passphrase(request, object_id):

    volume = models.Volume.objects.get(id=object_id)
    if request.method == "POST":
        form = forms.CreatePassphraseForm(request.POST)
        if form.is_valid():
            try:
                form.done(volume=volume)
                return JsonResp(
                    request,
                    message=_("Passphrase created"))
            except ClientException as e:
                form._errors['__all__'] = form.error_class([str(e)])
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
        if form.is_valid() and form.done(volume=volume):
            return JsonResp(
                request,
                message=_("Passphrase updated"))
    else:
        form = forms.ChangePassphraseForm()
    return render(request, "storage/change_passphrase.html", {
        'volume': volume,
        'form': form,
    })


def volume_lock(request, object_id):
    volume = models.Volume.objects.get(id=object_id)
    assert(volume.vol_encrypt > 0)

    if request.method == "POST":

        _n = notifier()
        if '__confirm' not in request.POST and not _n.is_freenas() and _n.failover_licensed():
            remaining_volumes = [v for v in models.Volume.objects.exclude(pk=object_id) if v.is_decrypted()]

            if not remaining_volumes:
                message = render_to_string('freeadmin/generic_model_confirm.html', {
                    'message': 'Warning: Locking this volume will prevent failover from functioning correctly.<br />Do you want to continue?',
                })
                return JsonResp(request, confirm=message)

        with client as c:
            c.call('pool.lock', volume.id, job=True)

        """
        if hasattr(notifier, 'failover_status') and notifier().failover_status() == 'MASTER':
            from freenasUI.failover.enc_helper import LocalEscrowCtl
            escrowctl = LocalEscrowCtl()
            escrowctl.clear()
            try:
                os.unlink('/tmp/.failover_master')
            except Exception:
                pass
            try:
                with client as c:
                    c.call('failover.call_remote', 'failover.encryption_clearkey')
            except Exception:
                log.warn('Failed to clear key on standby node, is it down?', exc_info=True)
        """
        return JsonResp(request, message=_("Volume locked"))
    return render(request, "storage/lock.html")


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
            try:
                form.done(volume)
            except MiddlewareError as e:
                form._errors['__all__'] = form.error_class([
                    _(str(e))
                ])
                return JsonResp(request, form=form)
            else:
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
        return HttpResponseRedirect('/legacy/')

    geli_keyfile = volume.get_geli_keyfile()
    with open(geli_keyfile, 'rb') as f:
        wrapper = FileWrapper(f)

        response = HttpResponse(wrapper, content_type='application/octet-stream')
        response['Content-Length'] = os.path.getsize(geli_keyfile)
        response['Content-Disposition'] = 'attachment; filename=geli.key'
        del request.session["allow_gelikey"]
        return response


def volume_rekey(request, object_id):

    _n = notifier()
    standby_offline = False
    if not _n.is_freenas() and _n.failover_licensed():
        try:
            with client as c:
                c.call('failover.call_remote', 'core.ping')
        except Exception:
            standby_offline = True

    volume = models.Volume.objects.get(id=object_id)
    if request.method == "POST":
        form = forms.ReKeyForm(request.POST, volume=volume)
        if form.is_valid() and form.done():
            return JsonResp(
                request,
                message=_("Encryption re-key succeeded"))
    else:
        form = forms.ReKeyForm(volume=volume)

    return render(request, "storage/rekey.html", {
        'form': form,
        'volume': volume,
        'standby_offline': standby_offline,
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
        return HttpResponseRedirect('/legacy/')

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


def volume_upgrade(request, object_id):
    volume = models.Volume.objects.get(pk=object_id)

    if request.method == 'POST':
        with client as c:
            c.call('pool.upgrade', object_id)

        return JsonResp(request, message=_('The pool has been upgraded'))

    return render(request, 'storage/upgrade_confirm.html', {
        'volume': volume,
    })


def disk_editbulk(request):

    if request.method == "POST":
        ids = request.POST.get("ids", "").split(",")
        disks = models.Disk.objects.filter(pk__in=ids)
        form = forms.DiskEditBulkForm(request.POST, disks=disks)
        if form.is_valid():
            form.save()
            return JsonResp(
                request,
                message=_("Disks successfully edited"))

        return JsonResp(request, form=form)
    else:
        ids = request.GET.get("ids", "").split(",")
        disks = models.Disk.objects.filter(pk__in=ids)
        form = forms.DiskEditBulkForm(disks=disks)

    return render(request, "storage/disk_editbulk.html", {
        'form': form,
        'disks': ', '.join([disk.disk_name for disk in disks]),
    })


def vmwareplugin_datastores(request):
    data = {
        'error': False,
    }
    if request.POST.get('oid'):
        vmware = models.VMWarePlugin.objects.get(id=request.POST.get('oid'))
    else:
        vmware = None
    try:
        if request.POST.get('password'):
            password = request.POST.get('password')
        elif not request.POST.get('password') and vmware:
            password = vmware.get_password()
        else:
            password = ''
        with client as c:
            ds = c.call('vmware.get_datastores', {
                'hostname': request.POST.get('hostname'),
                'username': request.POST.get('username'),
                'password': password,
            })
        data['value'] = []
        for i in ds.values():
            data['value'] += i.keys()
    except Exception as e:
        data['error'] = True
        data['errmsg'] = str(e)
    return HttpResponse(
        json.dumps(data),
        content_type='application/json',
    )


def tasks_json(request, dataset=None):
    tasks = []

    p = pipeopen("zfs list -H -o mountpoint,name")
    zfsout = p.communicate()[0].split('\n')
    if p.returncode != 0:
        zfsout = []

    task_list = []
    if dataset:
        mp = '/mnt/' + dataset
        for line in zfsout:
            if not line:
                continue

            try:
                zfs_mp, zfs_ds = line.split('\t')
                if mp == zfs_mp or mp.startswith("/%s/" % zfs_mp):
                    if mp == zfs_mp:
                        task_list = models.Task.objects.filter(
                            task_filesystem=zfs_ds
                        )
                    else:
                        task_list = models.Task.objects.filter(
                            Q(task_filesystem=zfs_ds) &
                            Q(task_recursive=True)
                        )
                    break
            except Exception:
                pass

    else:
        task_list = models.Task.objects.order_by("task_filesystem").all()

    for task in task_list:
        t = {}
        for f in models.Task._meta.get_fields():
            if f.many_to_one or f.related_model:
                continue
            try:
                t[f.name] = str(getattr(task, f.name))
            except Exception:
                pass
        t['str'] = str(task)
        tasks.append(t)

    return HttpResponse(
        json.dumps(tasks),
        content_type='application/json'
    )


def tasks_dataset_json(request, dataset):
    return tasks_json(request, dataset)


def tasks_all_json(request):
    return tasks_json(request)


def tasks_recursive_json(request, dataset=None):
    tasks = []

    if dataset:
        task_list = models.Task.objects.order_by("task_filesystem").filter(
            Q(task_filesystem=dataset) &
            Q(task_recursive=True)
        )
    else:
        task_list = models.Task.objects.order_by("task_filesystem").filter(
            task_recursive=True
        )

    for task in task_list:
        t = {}
        for f in models.Task._meta.get_fields():
            if f.many_to_one or f.related_model:
                continue
            try:
                t[f.name] = str(getattr(task, f.name))
            except Exception:
                pass
        t['str'] = str(task)
        tasks.append(t)

    return HttpResponse(
        json.dumps(tasks),
        content_type='application/json'
    )


def tasks_all_recursive_json(request):
    return tasks_recursive_json(request)
