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
import os

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.utils import simplejson
from django.utils.translation import ugettext as _

#TODO remove import *
from dojango.util import to_dojo_data, json_encode
from freenasUI.services.models import *
from freenasUI.storage.forms import * 
from freenasUI.storage.models import * 
from freenasUI.services.models import services, CIFS, AFP, NFS 
from freenasUI.services.forms import CIFSForm, AFPForm, NFSForm 
from freenasUI.middleware.notifier import notifier
from freenasUI.common.system import get_freenas_version
import commands

## Disk section

@login_required
def storage(request):
    mp_list = MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
    variables = RequestContext(request, {
        'focused_tab' : 'storage',
        'mp_list': mp_list,
    })
    return render_to_response('storage/index.html', variables)

@login_required
def home(request):
    mp_list = MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
    en_dataset = MountPoint.objects.filter(mp_volume__vol_fstype__exact='ZFS').count() > 0
    zfsnap_list = notifier().zfs_snapshot_list()
    task_list = Task.objects.order_by("-id").all()
    variables = RequestContext(request, {
        'focused_tab': request.GET.get("tab", None),
        'en_dataset' : en_dataset,
        'mp_list': mp_list,
        'task_list': task_list,
        'zfsnap_list': zfsnap_list,
    })
    return render_to_response('storage/index2.html', variables)

@login_required
def wizard(request):

    if request.method == "POST":

        form = VolumeWizardForm(request.POST)
        if form.is_valid():
            form.done(request)

            return HttpResponse(simplejson.dumps({"error": False, "message": _("Volume") + " " + _("successfully added") + "."}), mimetype="application/json")
            #return render_to_response('storage/wizard_ok.html')
        else:

            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
    else:
        form = VolumeWizardForm()
        disks = []
    variables = RequestContext(request, {
        'form': form,
        'disks': disks
    })
    return render_to_response('storage/wizard2.html', variables)

@login_required
def volimport(request):

    if request.method == "POST":

        form = VolumeImportForm(request.POST)
        if form.is_valid():
            form.done(request)

            return HttpResponse(simplejson.dumps({"error": False, "message": _("Volume") + " " + _("successfully added") + "."}), mimetype="application/json")
            #return render_to_response('storage/wizard_ok.html')
        else:

            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
    else:
        form = VolumeImportForm()
        disks = []
    variables = RequestContext(request, {
        'form': form,
        'disks': disks
    })
    return render_to_response('storage/import.html', variables)

@login_required
def volautoimport(request):

    if request.method == "POST":

        form = VolumeAutoImportForm(request.POST)
        if form.is_valid():
            form.done(request)

            return HttpResponse(simplejson.dumps({"error": False, "message": _("Volume") + " " + _("successfully added") + "."}), mimetype="application/json")
            #return render_to_response('storage/wizard_ok.html')
        else:

            if 'volume_disks' in request.POST:
                disks = request.POST.getlist('volume_disks')
            else:
                disks = None
    else:
        form = VolumeAutoImportForm()
        disks = []
    variables = RequestContext(request, {
        'form': form,
        'disks': disks
    })
    return render_to_response('storage/autoimport.html', variables)

@login_required
def disks_datagrid(request, vid):

    names = [x.verbose_name for x in Disk._meta.fields]
    _n = [x.name for x in Disk._meta.fields]
    """
    Nasty hack to calculate the width of the datagrid column
    dojo DataGrid width="auto" doesnt work correctly and dont allow
         column resize with mouse
    """
    width = []
    for x in Disk._meta.fields:
        val = 8
        for letter in x.verbose_name:
            if letter.isupper():
                val += 10
            elif letter.isdigit():
                val += 9
            else:
                val += 7
        width.append(val)
    fields = zip(names, _n, width)

    variables = RequestContext(request, {
        'vid': vid,
        'app': 'storage',
        'model': 'Disk',
        'fields': fields,
    })
    return render_to_response('storage/datagrid_disks.html', variables)

def disks_datagrid_json(request, vid):

    volume = Volume.objects.get(pk=vid)
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
        if volume.vol_fstype in ('ZFS',):
            if data.disk_group.group_type == 'detached':
                ret['edit']['detach_url'] = reverse('storage_disk_detach', kwargs={'vid': vid, 'object_id': data.id})
            elif data.disk_group.group_type != 'cache':
                ret['edit']['replace_url'] = reverse('storage_disk_replacement', kwargs={'vid': vid, 'object_id': data.id})
        ret['edit'] = simplejson.dumps(ret['edit'])

        for f in data._meta.fields:
            if isinstance(f, models.ImageField) or isinstance(f, models.FileField): # filefields can't be json serialized
                ret[f.attname] = unicode(getattr(data, f.attname))
            else:
                ret[f.attname] = getattr(data, f.attname) #json_encode() this?
        fields = dir(data.__class__) + ret.keys()
        add_ons = [k for k in dir(data) if k not in fields]
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
        to_dojo_data(complete, identifier=Disk._meta.pk.name, num_rows=len(disks))
    ))

@login_required
def volume_disks(request, volume_id):
    # mp = MountPoint.objects.get(mp_volume = volume_id)
    volume = Volume.objects.get(id = volume_id)
    disk_list = Disk.objects.filter(disk_group__group_volume = volume_id)
    variables = RequestContext(request, {
        'focused_tab' : 'storage',
        'volume': volume,
        'disk_list': disk_list,
    })
    return render_to_response('storage/volume_detail.html', variables)

@login_required
def diskgroup_add_wrapper(request, *args, **kwargs):
    wiz = DiskGroupWizard([DiskGroupForm])
    return wiz(request, *args, **kwargs)

@login_required
def volume_create_wrapper(request, *args, **kwargs):
    wiz = VolumeWizard([VolumeForm])
    return wiz(request, *args, **kwargs)

@login_required
def dataset_create(request):
    mp_list = MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
    defaults = { 'dataset_compression' : 'inherit', 'dataset_atime' : 'inherit', }
    dataset_form = ZFSDataset_CreateForm(initial=defaults)
    if request.method == 'POST':
        dataset_form = ZFSDataset_CreateForm(request.POST)
        if dataset_form.is_valid():
            props = {}
            cleaned_data = dataset_form.cleaned_data
            volume = Volume.objects.get(id=cleaned_data.get('dataset_volid'))
            volume_name = volume.vol_name
            dataset_name = "%s/%s" % (volume_name, cleaned_data.get('dataset_name'))
            dataset_compression = cleaned_data.get('dataset_compression')
            if dataset_compression != 'inherit':
                props['compression']=dataset_compression.__str__()
            dataset_atime = cleaned_data.get('dataset_atime')
            if dataset_atime != 'inherit':
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
                mp = MountPoint(mp_volume=volume, mp_path='/mnt/%s' % (dataset_name), mp_options='noauto', mp_ischild=True)
                mp.save()
                return HttpResponseRedirect('/storage/')
            else:
                dataset_form.set_error(errmsg)
    variables = RequestContext(request, {
        'focused_tab' : 'storage',
        'mp_list': mp_list,
        'form': dataset_form,
        'freenas_version' : get_freenas_version(),
    })
    return render_to_response('storage/datasets.html', variables)

@login_required
def dataset_create2(request):
    mp_list = MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
    defaults = { 'dataset_compression' : 'inherit', 'dataset_atime' : 'inherit', }
    dataset_form = ZFSDataset_CreateForm(initial=defaults)
    if request.method == 'POST':
        dataset_form = ZFSDataset_CreateForm(request.POST)
        if dataset_form.is_valid():
            props = {}
            cleaned_data = dataset_form.cleaned_data
            volume = Volume.objects.get(id=cleaned_data.get('dataset_volid'))
            volume_name = volume.vol_name
            dataset_name = "%s/%s" % (volume_name, cleaned_data.get('dataset_name'))
            dataset_compression = cleaned_data.get('dataset_compression')
            if dataset_compression != 'inherit':
                props['compression']=dataset_compression.__str__()
            dataset_atime = cleaned_data.get('dataset_atime')
            if dataset_atime != 'inherit':
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
                mp = MountPoint(mp_volume=volume, mp_path='/mnt/%s' % (dataset_name), mp_options='noauto', mp_ischild=True)
                mp.save()
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Dataset") + " " + _("successfully added") + "."}), mimetype="application/json")
                #return render_to_response('storage/dataset_ok.html')
            else:
                dataset_form.set_error(errmsg)
    variables = RequestContext(request, {
        'focused_tab' : 'storage',
        'mp_list': mp_list,
        'form': dataset_form
    })
    return render_to_response('storage/datasets2.html', variables)

@login_required
def dataset_edit(request, object_id):
    mp = MountPoint.objects.get(pk=object_id)
    dataset_form = ZFSDataset_EditForm(mp=mp)
    if request.method == 'POST':
        dataset_form = ZFSDataset_EditForm(request.POST, mp=mp)
        if dataset_form.is_valid():
            volume = mp.mp_volume
            volume_name = volume.vol_name
            dataset_name = mp.mp_path.replace("/mnt/","")

            if dataset_form.cleaned_data["dataset_quota"] == "0":
                dataset_form.cleaned_data["dataset_quota"] = "none"
            if dataset_form.cleaned_data["dataset_refquota"] == "0":
                dataset_form.cleaned_data["dataset_refquota"] = "none"

            error = False
            if dataset_form.cleaned_data["dataset_compression"] == "inherit":
                error |= not notifier().zfs_inherit_option(dataset_name, "compression")
            else:
                error |= not notifier().zfs_set_option(dataset_name, "compression", dataset_form.cleaned_data["dataset_compression"])
            if dataset_form.cleaned_data["dataset_atime"] == "inherit":
                error |= not notifier().zfs_inherit_option(dataset_name, "atime")
            else:
                error |= not notifier().zfs_set_option(dataset_name, "atime", dataset_form.cleaned_data["dataset_atime"])
            error |= not notifier().zfs_set_option(dataset_name, "reservation", dataset_form.cleaned_data["dataset_reserv"])
            error |= not notifier().zfs_set_option(dataset_name, "refreservation", dataset_form.cleaned_data["dataset_refreserv"])
            error |= not notifier().zfs_set_option(dataset_name, "quota", dataset_form.cleaned_data["dataset_quota"])
            error |= not notifier().zfs_set_option(dataset_name, "refquota", dataset_form.cleaned_data["dataset_refquota"])

            if not error:
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Dataset") + " " + _("successfully edited") + "."}), mimetype="application/json")
            else:
                dataset_form.set_error(_("Some error ocurried while setting the options"))
    variables = RequestContext(request, {
        'mp': mp,
        'form': dataset_form
    })
    return render_to_response('storage/dataset_edit.html', variables)

@login_required
def zfsvolume_edit(request, object_id):
    mp = MountPoint.objects.get(pk=object_id)
    volume_form = ZFSVolume_EditForm(mp=mp)
    if request.method == 'POST':
        volume_form = ZFSVolume_EditForm(request.POST, mp=mp)
        if volume_form.is_valid():
            volume = mp.mp_volume
            volume_name = volume.vol_name
            volume_name = mp.mp_path.replace("/mnt/","")

            if volume_form.cleaned_data["volume_refquota"] == "0":
                volume_form.cleaned_data["volume_refquota"] = "none"

            error = False
            if volume_form.cleaned_data["volume_compression"] == "inherit":
                error |= not notifier().zfs_inherit_option(volume_name, "compression")
            else:
                error |= not notifier().zfs_set_option(volume_name, "compression", volume_form.cleaned_data["volume_compression"])
            if volume_form.cleaned_data["volume_atime"] == "inherit":
                error |= not notifier().zfs_inherit_option(volume_name, "atime")
            else:
                error |= not notifier().zfs_set_option(volume_name, "atime", volume_form.cleaned_data["volume_atime"])
            error |= not notifier().zfs_set_option(volume_name, "refreservation", volume_form.cleaned_data["volume_refreserv"])
            error |= not notifier().zfs_set_option(volume_name, "refquota", volume_form.cleaned_data["volume_refquota"])

            if not error:
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Native dataset") + " " + _("successfully edited") + "."}), mimetype="application/json")
            else:
                volume_form.set_error(_("Some error ocurried while setting the options"))
    variables = RequestContext(request, {
        'mp': mp,
        'form': volume_form
    })
    return render_to_response('storage/volume_edit.html', variables)

@login_required
def mp_permission(request, object_id):
    mp = MountPoint.objects.get(id = object_id)
    mp_list = MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
    if request.method == 'POST':
        form = MountPointAccessForm(request.POST)
        if form.is_valid():
            mp_path=mp.mp_path.__str__()
            form.commit(path=mp_path)
            return HttpResponseRedirect('/storage/')
    else:
        form = MountPointAccessForm()
    variables = RequestContext(request, {
        'focused_tab' : 'storage',
        'mp': mp,
        'mp_list': mp_list,
        'form': form,
        'freenas_version' : get_freenas_version(),
    })
    return render_to_response('storage/permission.html', variables)

@login_required
def mp_permission2(request, object_id):
    mp = MountPoint.objects.get(id = object_id)
    mp_list = MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
    if request.method == 'POST':
        form = MountPointAccessForm(request.POST)
        if form.is_valid():
            mp_path=mp.mp_path.__str__()
            form.commit(path=mp_path)
            return HttpResponse(simplejson.dumps({"error": False, "message": "Mount Point permissions successfully updated."}), mimetype="application/json")
            #return HttpResponseRedirect('/storage/')
    else:
        form = MountPointAccessForm(initial={'path':mp.mp_path})
    variables = RequestContext(request, {
        'mp': mp,
        'mp_list': mp_list,
        'form': form,
    })
    return render_to_response('storage/permission2.html', variables)

@login_required
def dataset_delete(request, object_id):
    obj = MountPoint.objects.get(id=object_id)
    if request.method == 'POST':
        notifier().destroy_zfs_dataset(path = obj.mp_path[5:].__str__())
        obj.delete()
        return HttpResponseRedirect('/storage/')
    else:
        c = RequestContext(request, {
            'focused_tab' : 'storage',
            'object': obj,
        })
        return render_to_response('storage/dataset_confirm_delete.html', c)

@login_required
def dataset_delete2(request, object_id):
    obj = MountPoint.objects.get(id=object_id)
    if request.method == 'POST':
        retval = notifier().destroy_zfs_dataset(path = obj.mp_path[5:].__str__())
        if retval == '':
            obj.delete()
            return HttpResponse(simplejson.dumps({"error": False, "message": "Dataset successfully destroyed."}), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps({"error": True, "message": retval}), mimetype="application/json")
    else:
        c = RequestContext(request, {
            'focused_tab' : 'storage',
            'object': obj,
        })
        return render_to_response('storage/dataset_confirm_delete2.html', c)

@login_required
def snapshot_delete2(request, dataset, snapname):
    snapshot = '%s@%s' % (dataset, snapname)
    if request.method == 'POST':
        notifier().destroy_zfs_dataset(path = snapshot.__str__())
        return HttpResponse(simplejson.dumps({"error": False, "message": "Snapshot successfully deleted."}), mimetype="application/json")
    else:
        c = RequestContext(request, {
            'snapname' : snapname,
            'dataset' : dataset,
        })
        return render_to_response('storage/snapshot_confirm_delete2.html', c)

@login_required
def snapshot_rollback2(request, dataset, snapname):
    snapshot = '%s@%s' % (dataset, snapname)
    if request.method == "POST":
        ret = notifier().rollback_zfs_snapshot(snapshot = snapshot.__str__())
        if ret == '':
            return HttpResponse(simplejson.dumps({"error": False, "message": "Rollback successful."}), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps({"error": True, "message": ret}), mimetype="application/json")
    else:
        c = RequestContext(request, {
            'snapname' : snapname,
            'dataset' : dataset,
        })
        return render_to_response('storage/snapshot_confirm_rollback2.html', c)

@login_required
def periodicsnap(request):

    if request.method == "POST":

        form = PeriodicSnapForm(request.POST)
        if form.is_valid():
            form.save()

            return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshot") + " " + _("successfully added") + "."}), mimetype="application/json")
    else:
        form = PeriodicSnapForm()
    variables = RequestContext(request, {
        'form': form,
        'extra_js': Task._admin.extra_js,
    })
    return render_to_response('storage/periodicsnap.html', variables)

@login_required
def manualsnap(request, path):
    if request.method == "POST":
        form = ManualSnapshotForm(request.POST)
        if form.is_valid():
            form.commit(path)
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshot successfully taken")}), mimetype="application/json")
    else:
        form = ManualSnapshotForm()
    variables = RequestContext(request, {
        'form': form,
        'path': path,
    })
    return render_to_response('storage/manualsnap.html', variables)

@login_required
def clonesnap(request, snapshot):
    initial = { 'cs_snapshot' : snapshot }
    if request.method == "POST":
        form = CloneSnapshotForm(request.POST, initial=initial)
        if form.is_valid():
            retval = form.commit()
            if retval == '':
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Snapshot successfully cloned")}), mimetype="application/json")
            else:
                return HttpResponse(simplejson.dumps({"error": True, "message": retval}), mimetype="application/json")
    else:
        form = CloneSnapshotForm(initial=initial)
    variables = RequestContext(request, {
        'form': form,
        'snapshot': snapshot,
    })
    return render_to_response('storage/clonesnap.html', variables)

@login_required
def disk_replacement(request, vid, object_id):

    volume = Volume.objects.get(pk=vid)
    fromdisk = Disk.objects.get(pk=object_id)

    if request.method == "POST":
        form = DiskReplacementForm(request.POST, disk=fromdisk)
        if form.is_valid():
            devname = form.cleaned_data['volume_disks']
            if devname != fromdisk.disk_name:
                disk = Disk()
                disk.disk_disks = devname
                disk.disk_name = devname
                disk.disk_group = fromdisk.disk_group
                disk.disk_description = fromdisk.disk_description
                disk.save()
                rv = notifier().zfs_replace_disk(vid, object_id, unicode(disk.id))
            else: 
                rv = notifier().zfs_replace_disk(vid, object_id, object_id)
            if rv == 0:
                if devname != fromdisk.disk_name:
                    dg = DiskGroup.objects.filter(group_volume=volume,group_type='detached')
                    if dg.count() == 0:
                        dg = DiskGroup()
                        dg.group_volume = volume
                        dg.group_name = "%sdetached" % volume.vol_name
                        dg.group_type = 'detached'
                        dg.save()
                    else:
                        dg = dg[0]
                    fromdisk.disk_group = dg
                    fromdisk.save()
                return HttpResponse(simplejson.dumps({"error": False, "message": _("Disk replacement has been successfully done.")}), mimetype="application/json")
            else:
                return HttpResponse(simplejson.dumps({"error": True, "message": _("Some error ocurried.")}), mimetype="application/json")

    else:
        form = DiskReplacementForm(disk=fromdisk)
    variables = RequestContext(request, {
        'form': form,
        'vid': vid,
        'object_id': object_id,
        'fromdisk': fromdisk,
    })
    return render_to_response('storage/disk_replacement.html', variables)

@login_required
def disk_detach(request, vid, object_id):

    volume = Volume.objects.get(pk=vid)
    disk = Disk.objects.get(pk=object_id)

    if request.method == "POST":
        dg = DiskGroup.objects.filter(group_volume=volume,group_type='detached')
        if dg.count() == 0:
            dg = DiskGroup()
            dg.group_volume = volume
            dg.group_name = "%sdetached" % volume.vol_name
            dg.group_type = 'detached'
            dg.save()
        else:
            dg = dg[0]
        rv = notifier().zfs_detach_disk(vid, object_id)
        if rv == 0:
            disk.disk_group = dg
            disk.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Disk detach has been successfully done.")}), mimetype="application/json")
        else:
            return HttpResponse(simplejson.dumps({"error": True, "message": _("Some error ocurried.")}), mimetype="application/json")

    variables = RequestContext(request, {
        'vid': vid,
        'object_id': object_id,
        'disk': disk,
    })
    return render_to_response('storage/disk_detach.html', variables)
