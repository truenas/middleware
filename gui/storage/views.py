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
import ssl
import subprocess
import traceback
import sys
import urllib
from time import sleep

from wsgiref.util import FileWrapper
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext as _

from freenasUI.common import humanize_size
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.system import is_mounted
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware import zfs
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.system.models import Advanced
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.services.models import iSCSITargetExtent
from freenasUI.storage import forms, models
import socket

log = logging.getLogger('storage.views')


# FIXME: Move to a utils module
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

    view = appPool.hook_app_index('storage', request)
    view = filter(None, view)
    if view:
        return view[0]

    tabs = appPool.hook_app_tabs('storage', request)
    return render(request, 'storage/index.html', {
        'focused_tab': request.GET.get("tab", 'storage.Volumes.View'),
        'hook_tabs': tabs,
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

    return HttpResponse(json.dumps(data))


def snapshots(request):
    return render(request, 'storage/snapshots.html')


def volumemanager(request):

    if request.method == "POST":
        form = forms.VolumeManagerForm(request.POST)
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

    _n = notifier()
    disks = []
    # Grab disk list
    # Root device already ruled out
    for disk, info in _n.get_disks().items():
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

    bysize = OrderedDict(sorted(bysize.iteritems(), reverse=True))

    swap = Advanced.objects.latest('id').adv_swapondrive

    encwarn = (
        u'<span style="color: red; font-size:110%%;">%s</span>'
        u'<p>%s</p>'
        u'<p>%s</p>'
        u'<p>%s</p>'
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
    qs = models.Volume.objects.filter(vol_fstype='ZFS')
    for vol in qs:
        if not vol.is_decrypted():
            continue
        try:
            _n.zpool_parse(vol.vol_name)
        except:
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
        if form.is_valid():
            events = []
            form.done(request, events)
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
                for i in request.POST.keys() if zpoolfields.match(i)
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


SOCKIMP = '/var/run/importcopy/importsock'


def get_import_progress_from_socket(s=None, n=4096):
    data = ''
    close_sock = False
    try:
        if s is None:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(SOCKIMP)
            s.setblocking(0)
            close_sock = True
        s.send("get_progress")
        packet = s.recv(n)
        while packet:
            data += packet
            packet = s.recv(n)
    except socket.error:
        pass
    finally:
        if close_sock:
            s.close()
    return data


def final_importdisk_return_response(data, abort=False):
    stdout_data = False
    if data['stdout_file']:
            with open(data['stdout_file'], 'rUb') as f:
                stdout_data = f.read().decode('utf8')
    return {
        'vol': data["volume"],
        'error': data.get("error", False),
        'abort': abort,
        'traceback': data.get("traceback", False),
        'stdout': stdout_data
    }


def volimport(request):
    if os.path.exists(SOCKIMP):
        try:
            data = json.loads(get_import_progress_from_socket())
            if data["status"] in ["finished", "error"]:
                return render(
                    request, 'storage/import_stats.html', final_importdisk_return_response(data)
                )
            return render(request, 'storage/import_progress.html')
        except Exception as e:
            data = {
                'vol': '',
                'status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc() if sys.exc_info()[0] else False
            }
            return render(request, 'storage/import_stats.html', data)

    if request.method == "POST":
        form = forms.VolumeImportForm(request.POST)
        if form.is_valid():
            form.done(request)
            # usage for command below
            # Usage: sockscopy vol_to_import fs_type dest_path socket_path
            subprocess.Popen([
                "/usr/local/bin/sockscopy",
                "/dev/{0}".format(form.cleaned_data.get('volume_disks')),
                form.cleaned_data.get('volume_fstype').lower(),
                form.cleaned_data.get('volume_dest_path'),
                SOCKIMP
            ])
            # give the background disk import code time to create a socket
            sleep(2)
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
    return HttpResponse(get_import_progress_from_socket(), content_type='application/json')


def volimport_abort(request):
    if request.method == 'POST':
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCKIMP)
        s.setblocking(0)
        try:
            data = json.loads(get_import_progress_from_socket(s))
        except Exception as e:
            data = {
                'vol': '',
                'status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc() if sys.exc_info()[0] else False
            }
        if data["status"] == "finished":
            s.send("done")
            s.close()
            return JsonResp(request, message=_("Volume successfully Imported."))
        if data["status"] == "error":
            s.send("stop")
            s.close()
            return JsonResp(request, message=_("Error Importing Volume"))
        s.send("stop")
        s.close()
        return render(
            request,
            'storage/import_stats.html',
            final_importdisk_return_response(data, abort=True)
        )


def dataset_create(request, fs):
    defaults = {'dataset_compression': 'inherit', 'dataset_atime': 'inherit'}
    if request.method == 'POST':
        dataset_form = forms.ZFSDataset(request.POST, fs=fs)
        if dataset_form.is_valid():
            props = {}
            cleaned_data = dataset_form.cleaned_data
            dataset_name = "%s/%s" % (fs, cleaned_data.get('dataset_name'))
            dataset_compression = cleaned_data.get('dataset_compression')
            dataset_share_type = cleaned_data.get('dataset_share_type')
            if dataset_share_type == "windows":
                props['aclmode'] = 'restricted'
            props['casesensitivity'] = cleaned_data.get(
                'dataset_case_sensitivity'
            )
            props['compression'] = dataset_compression.__str__()
            dataset_atime = cleaned_data.get('dataset_atime')
            props['atime'] = dataset_atime.__str__()
            refquota = cleaned_data.get('dataset_refquota')
            if refquota != '0':
                props['refquota'] = refquota.__str__()
            quota = cleaned_data.get('dataset_quota')
            if quota != '0':
                props['quota'] = quota.__str__()
            refreservation = cleaned_data.get('dataset_refreservation')
            if refreservation != '0':
                props['refreservation'] = refreservation.__str__()
            refreservation = cleaned_data.get('dataset_reservation')
            if refreservation != '0':
                props['refreservation'] = refreservation.__str__()
            dedup = cleaned_data.get('dataset_dedup')
            if dedup != 'inherit':
                props['dedup'] = dedup.__str__()
            recordsize = cleaned_data.get('dataset_recordsize')
            if recordsize:
                props['recordsize'] = recordsize
            dataset_comments = cleaned_data.get('dataset_comments')
            errno, errmsg = notifier().create_zfs_dataset(
                path=str(dataset_name),
                props=props)
            notifier().zfs_set_option(name=str(dataset_name), item="org.freenas:description", value=dataset_comments)
            if errno == 0:
                if dataset_share_type == "unix":
                    notifier().dataset_init_unix(dataset_name)
                elif dataset_share_type == "windows":
                    notifier().dataset_init_windows(dataset_name)
                elif dataset_share_type == "mac":
                    notifier().dataset_init_apple(dataset_name)
                return JsonResp(
                    request,
                    message=_("Dataset successfully added."))
            else:
                dataset_form.set_error(errmsg)
                return JsonResp(request, form=dataset_form)
        else:
            return JsonResp(request, form=dataset_form)
    else:
        dataset_form = forms.ZFSDataset(initial=defaults, fs=fs)
    return render(request, 'storage/datasets.html', {
        'form': dataset_form,
        'fs': fs,
    })


def dataset_edit(request, dataset_name):
    if request.method == 'POST':
        dataset_form = forms.ZFSDataset(
            request.POST, fs=dataset_name, create=False
        )
        if dataset_form.is_valid():
            if dataset_form.cleaned_data["dataset_quota"] == "0":
                dataset_form.cleaned_data["dataset_quota"] = "none"
            if dataset_form.cleaned_data["dataset_refquota"] == "0":
                dataset_form.cleaned_data["dataset_refquota"] = "none"

            error = False
            errors = {}

            for attr in (
                'org.freenas:description',
                'compression',
                'atime',
                'dedup',
                'reservation',
                'refreservation',
                'quota',
                'refquota',
                'share_type'
            ):
                if attr == 'org.freenas:description':
                    formfield = 'dataset_comments'
                else:
                    formfield = 'dataset_%s' % attr
                val = dataset_form.cleaned_data[formfield]

                if val == "inherit":
                    success, err = notifier().zfs_inherit_option(
                        dataset_name,
                        attr)
                else:
                    if attr == "share_type":
                        notifier().change_dataset_share_type(
                            dataset_name, val)
                    else:
                        success, err = notifier().zfs_set_option(
                            dataset_name,
                            attr,
                            val)
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
        dataset_form = forms.ZFSDataset(fs=dataset_name, create=False)
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
            zvol_volsize = cleaned_data.get('zvol_volsize')
            zvol_blocksize = cleaned_data.get("zvol_blocksize")
            zvol_name = "%s/%s" % (parent, cleaned_data.get('zvol_name'))
            zvol_comments = cleaned_data.get('zvol_comments')
            zvol_compression = cleaned_data.get('zvol_compression')
            props['compression'] = str(zvol_compression)
            if zvol_blocksize:
                props['volblocksize'] = zvol_blocksize
            errno, errmsg = notifier().create_zfs_vol(
                name=str(zvol_name),
                size=str(zvol_volsize),
                sparse=cleaned_data.get("zvol_sparse", False),
                props=props)
            notifier().zfs_set_option(name=str(zvol_name), item="org.freenas:description", value=zvol_comments)
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
        form = forms.ZvolDestroyForm(request.POST, fs=name)
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
        if form.is_valid():
            retval = notifier().destroy_zfs_vol(name, recursive=True)
            if retval == '':
                return JsonResp(
                    request,
                    message=_("ZFS Volume successfully destroyed."))
            else:
                return JsonResp(request, error=True, message=retval)
    else:
        form = forms.ZvolDestroyForm(fs=name)
    return render(request, 'storage/zvol_confirm_delete.html', {
        'form': form,
        'name': name,
    })


def zvol_edit(request, name):

    if request.method == 'POST':
        form = forms.ZVol_EditForm(request.POST, name=name)
        if form.is_valid():

            _n = notifier()
            error, errors = False, {}
            for attr, formfield, can_inherit in (
                ('org.freenas:description', 'zvol_comments', False),
                ('compression', None, True),
                ('dedup', None, True),
                ('volsize', None, True),
            ):
                if not formfield:
                    formfield = 'zvol_%s' % attr
                if can_inherit and form.cleaned_data[formfield] == "inherit":
                    success, err = _n.zfs_inherit_option(
                        name,
                        attr)
                else:
                    success, err = _n.zfs_set_option(
                        name,
                        attr,
                        form.cleaned_data[formfield])
                if not success:
                    error = True
                    errors[formfield] = err

            if not error:
                extents = iSCSITargetExtent.objects.filter(
                    iscsi_target_extent_type='ZVOL',
                    iscsi_target_extent_path='zvol/' + name)
                if extents.exists():
                    _n.reload("iscsitarget")
                return JsonResp(
                    request,
                    message=_("Zvol successfully edited."))
            else:
                for field, err in errors.items():
                    form._errors[field] = form.error_class([
                        err,
                    ])
        else:
            return JsonResp(request, form=form)
    else:
        form = forms.ZVol_EditForm(name=name)
    return render(request, 'storage/volume_edit.html', {
        'form': form,
    })


def mp_permission(request, path):
    path = urllib.unquote_plus(path)
    # FIXME: dojo cannot handle urls partially urlencoded %2F => /
    if not path.startswith('/'):
        path = '/' + path
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

    volume = models.Volume.objects.get(pk=vid)
    usedbytes = volume._get_used_bytes()
    usedsize = humanize_size(usedbytes)
    services = {
        key: val
        for key, val in volume.has_attachments().items() if len(val) > 0
    }
    if volume.vol_encrypt > 0:
        request.session["allow_gelikey"] = True
    if request.method == "POST":
        form = forms.VolumeExport(
            request.POST,
            instance=volume,
            services=services)
        if form.is_valid():
            try:
                events = []
                volume.delete(
                    destroy=form.cleaned_data['mark_new'],
                    cascade=form.cleaned_data.get('cascade', True))
                form.done(request, events)
                return JsonResp(
                    request,
                    message=_("The volume has been successfully detached"),
                    events=events,
                )
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
            return JsonResp(
                request,
                message=_("The scrub process has stopped"),
            )
        else:
            notifier().zfs_scrub(str(volume.vol_name))
            return JsonResp(request, message=_("The scrub process has begun"))

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
        if form.is_valid():
            if form.done():
                return JsonResp(
                    request,
                    message=_("Disk replacement has been initiated."))
            else:
                return JsonResp(
                    request,
                    error=True,
                    message=_("An error occurred."))

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

    form = forms.DiskWipeForm()
    if request.method == "POST":
        form = forms.DiskWipeForm(request.POST)
        if form.is_valid():
            mounted = []
            for geom in notifier().disk_get_consumers(devname):
                gname = geom.xpath("./name")[0].text
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
    details = 'Starting Disk Wipe'
    indeterminate = True
    progress = 0
    step = 1
    finished = False
    error = False
    pidfile = '/var/tmp/disk_wipe_%s.pid' % (devname, )
    if not os.path.exists(pidfile):
        return HttpResponse('new Object({state: "starting"});')

    with open(pidfile, 'r') as f:
        pid = f.read()

    try:
        os.kill(int(pid), signal.SIGINFO)
        received = 0
        size = 0
        indeterminate = False
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
                details = 'Wiping Disk...'
                if received == size:
                    finished = True
                    progress = 100
                else:
                    try:
                        progress = int(float(received) / float(size) * 100)
                    except:
                        pass

    except Exception, e:
        log.warn("Could not check for disk wipe progress: %s", e)
        indeterminate = True

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


def volume_lock(request, object_id):
    volume = models.Volume.objects.get(id=object_id)
    assert(volume.vol_encrypt > 0)

    if request.method == "POST":
        notifier().volume_detach(volume)
        if hasattr(notifier, 'failover_status'):
            if notifier().failover_status() == 'MASTER':
                from freenasUI.failover.enc_helper import LocalEscrowCtl
                escrowctl = LocalEscrowCtl()
                escrowctl.clear()
                try:
                    os.unlink('/tmp/.failover_master')
                except:
                    pass
        notifier().restart("system_datasets")
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

    _n = notifier()
    standby_offline = False
    if not _n.is_freenas() and _n.failover_licensed():
        s = _n.failover_rpc()
        try:
            s.ping()
        except:
            standby_offline = True

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


def volume_upgrade(request, object_id):
    volume = models.Volume.objects.get(pk=object_id)
    try:
        notifier().zpool_version(volume.vol_name)
    except:
        raise MiddlewareError(
            _('Pool output could not be parsed. Is the pool imported?')
        )
    if request.method == "POST":
        upgrade = notifier().zpool_upgrade(str(volume.vol_name))
        if upgrade is not True:
            return JsonResp(
                request,
                message=_("The pool failed to upgraded: %s") % upgrade,
            )
        else:
            return JsonResp(request, message=_("The pool has been upgraded"))

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
    from pysphere import VIServer
    ssl._create_default_https_context = ssl._create_unverified_context
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
        server = VIServer()
        server.connect(
            request.POST.get('hostname'),
            request.POST.get('username'),
            password,
            sock_timeout=7,
        )
        data['value'] = server.get_datastores().values()
        server.disconnect()
    except Exception, e:
        data['error'] = True
        data['errmsg'] = unicode(e).encode('utf8')
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
            except:
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
            except:
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
            except:
                pass
        t['str'] = str(task)
        tasks.append(t)

    return HttpResponse(
        json.dumps(tasks),
        content_type='application/json'
    )


def tasks_all_recursive_json(request):
    return tasks_recursive_json(request)
