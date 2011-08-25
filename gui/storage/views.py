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
import re

from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.http import HttpResponse
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.db import transaction, models as dmodels

from dojango.util import to_dojo_data
from freenasUI.services.models import iSCSITargetExtent
from freenasUI.storage import forms
from freenasUI.storage import models
from freenasUI.storage.evilhack import evil_zvol_destroy
from freenasUI.middleware.notifier import notifier
from middleware.exceptions import MiddlewareError

## Disk section

def home(request):
    return render(request, 'storage/index.html', {
        'focused_tab': request.GET.get("tab", None),
    })

def tasks(request):
    task_list = models.Task.objects.order_by("-id").all()
    return render(request, 'storage/tasks.html', {
        'task_list': task_list,
        })

def volumes(request):
    en_dataset = models.MountPoint.objects.filter(mp_volume__vol_fstype__exact='ZFS').count() > 0
    mp_list = models.MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
    zvols = {}
    for volume in models.Volume.objects.filter(vol_fstype__exact='ZFS'):
        zvol = notifier().list_zfs_vols(volume.vol_name)
        zvols[volume.vol_name] = zvol
    return render(request, 'storage/volumes.html', {
        'mp_list': mp_list,
        'en_dataset' : en_dataset,
        'zvols': zvols,
        })

def replications(request):
    zfsrepl_list = models.Replication.objects.select_related().all()
    return render(request, 'storage/replications.html', {
        'zfsrepl_list': zfsrepl_list,
        })

def snapshots(request):
    zfsnap_list = notifier().zfs_snapshot_list()
    return render(request, 'storage/snapshots.html', {
        'zfsnap_list': zfsnap_list,
        })

def snapshots_data(request):
    zfsnap = notifier().zfs_snapshot_list().items()
    zfsnap_list = []
    for vol, snaps in zfsnap:
        for snap in snaps:
            snap.update({
                'filesystem': vol,
            })
            zfsnap_list.append(snap)

    r = request.META.get("HTTP_RANGE", None)
    if r:
        r = r.split('=')[1].split('-')
        r1 = int(r[0])
        r2 = int(r[1]) + 1

    for key in request.GET.keys():
        reg = re.search(r'sort\((?P<sign>.)(?P<field>.+?)\)', key)
        if reg:
            sign, field = reg.groups()
            if sign == '-':
                rev = True
            else:
                rev = False
            if zfsnap_list[0].has_key(field):
                zfsnap_list.sort(key=lambda item:item[field], reverse=rev)

    data = []
    count = 0
    total = len(zfsnap_list)
    if r:
        zfsnap_list = zfsnap_list[r1:r2]
    for snap in zfsnap_list:
        snap['extra'] = simplejson.dumps({
            'clone_url': reverse('storage_clonesnap', kwargs={'snapshot': snap['fullname']}),
            'rollback_url': reverse('storage_snapshot_rollback', kwargs={'dataset': vol, 'snapname': snap['name']}) if snap['mostrecent'] else None,
            'delete_url': reverse('storage_snapshot_delete', kwargs={'dataset': vol, 'snapname': snap['name']}),
        })
        data.append(snap)
        count += 1

    if r:
        resp = HttpResponse(simplejson.dumps(data))
        resp['Content-Range'] = 'items %d-%d/%d' % (r1,r1+count, total)
    else:
        resp = HttpResponse(simplejson.dumps(data))
    return resp

def wizard(request):

    if request.method == "POST":

        form = forms.VolumeWizardForm(request.POST)
        if form.is_valid():
            try:
                form.done(request)
            except MiddlewareError, e:
                return HttpResponse(simplejson.dumps({"error": True, "message": _("Error: %s") % str(e)}), mimetype="application/json")
            else:
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Volume successfully added.")}), mimetype="application/json")
        else:
            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
            zpoolfields = re.compile(r'zpool_(.+)')
            zfsextra = [(zpoolfields.search(i).group(1), i, request.POST.get(i)) \
                        for i in request.POST.keys() if zpoolfields.match(i)]

    else:
        form = forms.VolumeWizardForm()
        disks = []
        zfsextra = None
    return render(request, 'storage/wizard.html', {
        'form': form,
        'disks': disks,
        'zfsextra': zfsextra,
    })

def volimport(request):

    if request.method == "POST":

        form = forms.VolumeImportForm(request.POST)
        if form.is_valid():
            form.done(request)
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Volume successfully added.")}), mimetype="application/json")
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

def volautoimport(request):

    if request.method == "POST":

        form = forms.VolumeAutoImportForm(request.POST)
        if form.is_valid():
            try:
                form.done(request)
            except MiddlewareError, e:
                return HttpResponse(simplejson.dumps({"error": True, "message": _("Error: %s") % str(e)}), mimetype="application/json")
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Volume successfully added.")}), mimetype="application/json")
        else:

            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
    else:
        form = forms.VolumeAutoImportForm()
        disks = []
    return render(request, 'storage/autoimport.html', {
        'form': form,
        'disks': disks
    })

def disks_datagrid(request, vid):

    names = [x.verbose_name for x in models.Disk._meta.fields]
    _n = [x.name for x in models.Disk._meta.fields]

    names.insert(2, _('Serial'))
    _n.insert(2, 'serial')
    """
    Nasty hack to calculate the width of the datagrid column
    dojo DataGrid width="auto" doesnt work correctly and dont allow
         column resize with mouse
    """
    width = []
    for x in names:
        val = 8
        for letter in x:
            if letter.isupper():
                val += 10
            elif letter.isdigit():
                val += 9
            else:
                val += 7
        width.append(val)
    fields = zip(names, _n, width)

    return render(request, 'storage/datagrid_disks.html', {
        'vid': vid,
        'app': 'storage',
        'model': 'Disk',
        'fields': fields,
    })

def disks_datagrid_json(request, vid):

    volume = models.Volume.objects.get(pk=vid)
    disks = []
    for dg in volume.diskgroup_set.all():
        for d in dg.disk_set.all():
            disks.append(d)

    complete = []
    for data in disks:
        ret = {}
        ret['edit'] = {
            'edit_url': reverse('freeadmin_model_edit', kwargs={'app':'storage', 'model': 'Disk', 'oid': data.id})+'?deletable=false',
            }
        if volume.vol_fstype == 'ZFS':
            if data.disk_group.group_type == 'detached':
                ret['edit']['detach_url'] = reverse('storage_disk_detach', kwargs={'vid': vid, 'object_id': data.id})
            elif data.disk_group.group_type != 'cache':
                ret['edit']['replace_url'] = reverse('storage_disk_replacement', kwargs={'vid': vid, 'object_id': data.id})

        elif volume.vol_fstype == 'UFS':
            state = notifier().geom_disk_state(data.disk_group.group_name, \
                                data.disk_group.group_type, data.disk_name)
            if data.disk_group.group_type in ('mirror', 'raid3') and \
                                        state not in ("SYNCHRONIZING",):
                ret['edit']['replace_url'] = reverse('storage_disk_replacement', kwargs={'vid': vid, 'object_id': data.id})
        ret['edit'] = simplejson.dumps(ret['edit'])

        for f in data._meta.fields:
            if isinstance(f, dmodels.ImageField) or isinstance(f, dmodels.FileField): # filefields can't be json serialized
                ret[f.attname] = unicode(getattr(data, f.attname))
            elif f.attname == 'disk_name':
                ret[f.attname] = notifier().identifier_to_device(data.disk_identifier)
                ret['serial'] = data.get_serial() or _('Unknown')
            else:
                ret[f.attname] = getattr(data, f.attname) #json_encode() this?
        #fields = dir(data.__class__) + ret.keys()
        #add_ons = [k for k in dir(data) if k not in fields]
        #for k in add_ons:
        #    ret[k] = getattr(data, k)
        if request.GET.has_key('inclusions'):
            for k in request.GET['inclusions'].split(','):
                if k == "": continue
                try:
                    ret[k] = getattr(data,k)()
                except:
                    try:
                        ret[k] = eval("data.%s"%".".join(k.split("__")))
                    except:
                        ret[k] = getattr(data,k)
        complete.append(ret)

    return HttpResponse(simplejson.dumps(
        to_dojo_data(complete, identifier=models.Disk._meta.pk.name, num_rows=len(disks))
    ))

def volume_disks(request, volume_id):
    # mp = MountPoint.objects.get(mp_volume = volume_id)
    volume = models.Volume.objects.get(id = volume_id)
    disk_list = models.Disk.objects.filter(disk_group__group_volume = volume_id)
    return render(request, 'storage/volume_detail.html', {
        'focused_tab' : 'storage',
        'volume': volume,
        'disk_list': disk_list,
    })

def dataset_create(request):
    defaults = { 'dataset_compression' : 'inherit', 'dataset_atime' : 'inherit', }
    dataset_form = forms.ZFSDataset_CreateForm(initial=defaults)
    if request.method == 'POST':
        dataset_form = forms.ZFSDataset_CreateForm(request.POST)
        if dataset_form.is_valid():
            props = {}
            cleaned_data = dataset_form.cleaned_data
            volume = models.Volume.objects.get(id=cleaned_data.get('dataset_volid'))
            volume_name = volume.vol_name
            dataset_name = "%s/%s" % (volume_name, cleaned_data.get('dataset_name'))
            dataset_compression = cleaned_data.get('dataset_compression')
            props['compression']=dataset_compression.__str__()
            dataset_atime = cleaned_data.get('dataset_atime')
            props['atime']=dataset_atime.__str__()
            refquota = cleaned_data.get('dataset_refquota')
            if refquota != '0':
                props['refquota']=refquota.__str__()
            quota = cleaned_data.get('dataset_quota')
            if quota != '0':
                props['quota']=quota.__str__()
            refreservation = cleaned_data.get('dataset_refreserv')
            if refreservation != '0':
                props['refreservation']=refreservation.__str__()
            refreservation = cleaned_data.get('dataset_reserv')
            if refreservation != '0':
                props['refreservation']=refreservation.__str__()
            errno, errmsg = notifier().create_zfs_dataset(path=dataset_name.__str__(), props=props)
            if errno == 0:
                mp = models.MountPoint(mp_volume=volume, mp_path='/mnt/%s' % (dataset_name), mp_options='rw,late', mp_ischild=True)
                mp.save()
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Dataset successfully added.")}), mimetype="application/json")
            else:
                dataset_form.set_error(errmsg)
    return render(request, 'storage/datasets.html', {
        'focused_tab' : 'storage',
        'form': dataset_form
    })

def dataset_edit(request, object_id):
    mp = models.MountPoint.objects.get(pk=object_id)
    dataset_form = forms.ZFSDataset_EditForm(mp=mp)
    if request.method == 'POST':
        dataset_form = forms.ZFSDataset_EditForm(request.POST, mp=mp)
        if dataset_form.is_valid():
            dataset_name = mp.mp_path.replace("/mnt/","")
            if dataset_form.cleaned_data["dataset_quota"] == "0":
                dataset_form.cleaned_data["dataset_quota"] = "none"
            if dataset_form.cleaned_data["dataset_refquota"] == "0":
                dataset_form.cleaned_data["dataset_refquota"] = "none"

            error = False

            for attr in ('compression', 'atime'):
                formfield = 'dataset_%s' % attr
                if dataset_form.cleaned_data[formfield] == "inherit":
                    error |= not notifier().zfs_inherit_option(dataset_name, attr)
                else:
                    error |= not notifier().zfs_set_option(dataset_name, attr, dataset_form.cleaned_data[formfield])

            error |= not notifier().zfs_set_option(dataset_name, "reservation", dataset_form.cleaned_data["dataset_reservation"])
            error |= not notifier().zfs_set_option(dataset_name, "refreservation", dataset_form.cleaned_data["dataset_refreservation"])
            error |= not notifier().zfs_set_option(dataset_name, "quota", dataset_form.cleaned_data["dataset_quota"])
            error |= not notifier().zfs_set_option(dataset_name, "refquota", dataset_form.cleaned_data["dataset_refquota"])

            if not error:
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Dataset successfully edited.")}), mimetype="application/json")
            else:
                dataset_form.set_error(_("Some error ocurred while setting the options"))
    return render(request, 'storage/dataset_edit.html', {
        'mp': mp,
        'form': dataset_form
    })

def zvol_create(request):
    defaults = { 'zvol_compression' : 'inherit', }
    if request.method == 'POST':
        zvol_form = forms.ZVol_CreateForm(request.POST)
        if zvol_form.is_valid():
            props = {}
            cleaned_data = zvol_form.cleaned_data
            volume = models.Volume.objects.get(id=cleaned_data.get('zvol_volid'))
            volume_name = volume.vol_name
            zvol_size = cleaned_data.get('zvol_size')
            zvol_name = "%s/%s" % (volume_name, cleaned_data.get('zvol_name'))
            zvol_compression = cleaned_data.get('zvol_compression')
            props['compression']=zvol_compression.__str__()
            errno, errmsg = notifier().create_zfs_vol(name=zvol_name.__str__(), size=zvol_size.__str__(), props=props)
            if errno == 0:
                return HttpResponse(simplejson.dumps({"error": False, "message": _("ZFS Volume successfully added.")}), mimetype="application/json")
            else:
                zvol_form.set_error(errmsg)
    else:
        zvol_form = forms.ZVol_CreateForm(initial=defaults)
    return render(request, 'storage/zvols.html', {
        'form': zvol_form,
    })

def zvol_delete(request, name):

    if request.method == 'POST':
        try:
            retval = evil_zvol_destroy(name, iSCSITargetExtent, models.Disk, destroy=True)
        except ValueError:
            return HttpResponse(simplejson.dumps({"error": True, "message": _("This is in use by the iscsi target, please remove it there first.")}), mimetype="application/json")
        if retval == '':
            return HttpResponse(simplejson.dumps({"error": False, "message": _("ZFS Volume successfully destroyed.")}), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps({"error": True, "message": retval}), mimetype="application/json")
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
            volume_name = mp.mp_path.replace("/mnt/","")

            if volume_form.cleaned_data["volume_refquota"] == "0":
                volume_form.cleaned_data["volume_refquota"] = "none"

            error = False

            for attr in ('compression', 'atime'):
                formfield = 'volume_%s' % attr
                if volume_form.cleaned_data[formfield] == "inherit":
                    error |= not notifier().zfs_inherit_option(volume_name, attr)
                else:
                    error |= not notifier().zfs_set_option(volume_name, attr, volume_form.cleaned_data[formfield])

            error |= not notifier().zfs_set_option(volume_name, "refreservation", volume_form.cleaned_data["volume_refreservation"])
            error |= not notifier().zfs_set_option(volume_name, "refquota", volume_form.cleaned_data["volume_refquota"])

            if not error:
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Native dataset successfully edited.")}), mimetype="application/json")
            else:
                volume_form.set_error(_("Some error ocurred while setting the options"))
    return render(request, 'storage/volume_edit.html', {
        'mp': mp,
        'form': volume_form
    })

def mp_permission(request, object_id):
    mp = models.MountPoint.objects.get(id = object_id)
    if request.method == 'POST':
        form = forms.MountPointAccessForm(request.POST)
        if form.is_valid():
            mp_path=mp.mp_path.__str__()
            form.commit(path=mp_path)
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Mount Point permissions successfully updated.")}), mimetype="application/json")
    else:
        form = forms.MountPointAccessForm(initial={'path':mp.mp_path})
    return render(request, 'storage/permission.html', {
        'mp': mp,
        'form': form,
    })

def dataset_delete(request, object_id):
    obj = models.MountPoint.objects.get(id=object_id)
    if request.method == 'POST':
        retval = notifier().destroy_zfs_dataset(path = obj.mp_path[5:].__str__())
        if retval == '':
            obj.delete()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Dataset successfully destroyed.")}), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps({"error": True, "message": retval}), mimetype="application/json")
    else:
        return render(request, 'storage/dataset_confirm_delete.html', {
            'focused_tab' : 'storage',
            'object': obj,
        })

def snapshot_delete(request, dataset, snapname):
    snapshot = '%s@%s' % (dataset, snapname)
    if request.method == 'POST':
        retval = notifier().destroy_zfs_dataset(path = snapshot.__str__())
        if retval == '':
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshot successfully deleted.")}), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps({"error": True, "message": retval}), mimetype="application/json")
    else:
        return render(request, 'storage/snapshot_confirm_delete.html', {
            'snapname' : snapname,
            'dataset' : dataset,
        })

def snapshot_delete_bulk(request):

    snaps = request.POST.get("snaps", None)
    delete = request.POST.get("delete", None)
    if snaps and delete == "true":
        snap_list = snaps.split('|')
        for snapshot in snap_list:
            retval = notifier().destroy_zfs_dataset(path = snapshot.__str__())
            if retval != '':
                return HttpResponse(simplejson.dumps({"error": True, "message": retval}), mimetype="application/json")
        return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshots successfully deleted.")}), mimetype="application/json")

    return render(request, 'storage/snapshot_confirm_delete_bulk.html', {
        'snaps': snaps,
    })

def snapshot_rollback(request, dataset, snapname):
    snapshot = '%s@%s' % (dataset, snapname)
    if request.method == "POST":
        ret = notifier().rollback_zfs_snapshot(snapshot = snapshot.__str__())
        if ret == '':
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Rollback successful.")}), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps({"error": True, "message": ret}), mimetype="application/json")
    else:
        return render(request, 'storage/snapshot_confirm_rollback.html', {
            'snapname' : snapname,
            'dataset' : dataset,
        })

def periodicsnap(request):

    if request.method == "POST":

        form = forms.PeriodicSnapForm(request.POST)
        if form.is_valid():
            form.save()

            return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshot successfully added.")}), mimetype="application/json")
    else:
        form = forms.PeriodicSnapForm()
    return render(request, 'storage/periodicsnap.html', {
        'form': form,
        'extra_js': models.Task._admin.extra_js,
    })

def manualsnap(request, path):
    if request.method == "POST":
        form = forms.ManualSnapshotForm(request.POST)
        if form.is_valid():
            form.commit(path)
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshot successfully taken.")}), mimetype="application/json")
    else:
        form = forms.ManualSnapshotForm()
    return render(request, 'storage/manualsnap.html', {
        'form': form,
        'path': path,
    })

def clonesnap(request, snapshot):
    initial = { 'cs_snapshot' : snapshot }
    if request.method == "POST":
        form = forms.CloneSnapshotForm(request.POST, initial=initial)
        if form.is_valid():
            retval = form.commit()
            if retval == '':
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshot successfully cloned.")}), mimetype="application/json")
            else:
                return HttpResponse(simplejson.dumps({"error": True, "message": retval}), mimetype="application/json")
    else:
        form = forms.CloneSnapshotForm(initial=initial)
    return render(request, 'storage/clonesnap.html', {
        'form': form,
        'snapshot': snapshot,
    })

def disk_replacement(request, vid, object_id):

    volume = models.Volume.objects.get(pk=vid)
    fromdisk = models.Disk.objects.get(pk=object_id)

    if request.method == "POST":
        form = forms.DiskReplacementForm(request.POST, disk=fromdisk)
        if form.is_valid():
            try:
                if form.done(volume, fromdisk):
                    return HttpResponse(simplejson.dumps({"error": False, "message": _("Disk replacement has been initiated.")}), mimetype="application/json")
                else:
                    return HttpResponse(simplejson.dumps({"error": True, "message": _("Some error ocurred.")}), mimetype="application/json")
            except MiddlewareError, e:
                return HttpResponse(simplejson.dumps({"error": True, "message": _("Error: %s") % str(e)}), mimetype="application/json")

    else:
        form = forms.DiskReplacementForm(disk=fromdisk)
    return render(request, 'storage/disk_replacement.html', {
        'form': form,
        'vid': vid,
        'object_id': object_id,
        'fromdisk': fromdisk,
    })

def disk_detach(request, vid, object_id):

    volume = models.Volume.objects.get(pk=vid)
    disk = models.Disk.objects.get(pk=object_id)

    if request.method == "POST":
        notifier().zfs_detach_disk(volume, disk)
        dg = disk.disk_group
        disk.delete()
        # delete disk group if is now empty
        if models.Disk.objects.filter(disk_group=dg).count() == 0:
            dg.delete()
        return HttpResponse(simplejson.dumps({"error": False, "message": _("Disk detach has been successfully done.")}), mimetype="application/json")

    return render(request, 'storage/disk_detach.html', {
        'vid': vid,
        'object_id': object_id,
        'disk': disk,
    })


def volume_export(request, vid):

    from freenasUI.common import humanize_size
    volume = models.Volume.objects.get(pk=vid)
    usedbytes = sum([mp._get_used_bytes() for mp in volume.mountpoint_set.all()])
    usedsize = humanize_size(usedbytes)
    services = volume.has_attachments()
    if request.method == "POST":
        form = forms.VolumeExport(request.POST, instance=volume, services=services)
        if form.is_valid():
            volume.delete_step1(destroy=form.cleaned_data['mark_new'], cascade=form.cleaned_data.get('cascade', True))
            if volume.vol_fstype == 'ZFS' and not notifier().zfs_export(volume.vol_name):
                return HttpResponse(simplejson.dumps({"error": True, "message": _("The volume failed to export")}), mimetype="application/json")
            else:
                volume.delete_step2(destroy=form.cleaned_data['mark_new'], cascade=form.cleaned_data.get('cascade', True))
                return HttpResponse(simplejson.dumps({"error": False, "message": _("The volume has been successfully exported")}), mimetype="application/json")
    else:
        form = forms.VolumeExport(instance=volume, services=services)
    return render(request, 'storage/volume_export.html', {
        'volume': volume,
        'form': form,
        'used': usedsize,
        'services': services,
    })
