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

from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404, HttpResponse
from django.views.generic.list_detail import object_detail, object_list
from django.views.generic.create_update import update_object, delete_object
from django.utils import simplejson
from django.core import serializers
from django.utils.translation import ugettext as _

#TODO remove import *
from freenasUI.services.models import *
from freenasUI.storage.forms import * 
from freenasUI.storage.models import * 
from freenasUI.services.models import services, CIFS, AFP, NFS 
from freenasUI.services.forms import CIFSForm, AFPForm, NFSForm 
from freenasUI.middleware.notifier import notifier
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
    variables = RequestContext(request, {
        'en_dataset' : en_dataset,
        'mp_list': mp_list,
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

    from dojango.util import to_dojo_data, json_encode

    volume = Volume.objects.get(pk=vid)
    disks = []
    for dg in volume.diskgroup_set.all():
        for d in dg.disk_set.all():
            disks.append(d)

    complete = []
    for data in disks:
        ret = {}
        ret['edit'] = simplejson.dumps({
            'edit_url': reverse('freeadmin_model_edit', kwargs={'app':'storage', 'model': 'Disk', 'oid': data.id})+'?deletable=false'
            })
        for f in data._meta.fields:
            if isinstance(f, models.ImageField) or isinstance(f, models.           FileField): # filefields can't be json serialized
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
def diskgroup_list(request, template_name='freenas/disks/groups/diskgroup_list.html'):
    query_set = DiskGroup.objects.values().order_by('name')
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )


@login_required
def volume_create_wrapper(request, *args, **kwargs):
    wiz = VolumeWizard([VolumeForm])
    return wiz(request, *args, **kwargs)

@login_required
def volume_list(request, template_name='freenas/disks/volumes/volume_list.html'):
    query_set = Volume.objects.values().order_by('groups')
    #if len(query_set) == 0:
    #    raise Http404()
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )

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
        'form': dataset_form
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
        notifier().destroy_zfs_dataset(path = obj.mp_path[5:].__str__())
        obj.delete()
        return HttpResponse(simplejson.dumps({"error": False, "message": "Dataset successfully deleted."}), mimetype="application/json")
    else:
        c = RequestContext(request, {
            'focused_tab' : 'storage',
            'object': obj,
        })
        return render_to_response('storage/dataset_confirm_delete2.html', c)

@login_required
def generic_detail(request, object_id, model_name):
    storage_name_model_map = {
        'disk':		Disk,
        'diskgroup':	DiskGroup,
        'volume':	Volume,
    }
    model = storage_name_model_map[model_name]
    return object_detail(request, queryset=model.objects.all(), object_id=object_id)

@login_required
def generic_delete(request, object_id, model_name):
	storage_name_model_map = {
		'disk':	Disk,
		'group':	DiskGroup,
		'volume':	Volume,
	}
        # TODO: Extend delete_object to add a callback to do this
        # TODO: Recursively delete file extents as well
        if request.method == 'POST' and model_name == 'volume':
            vol = Volume.objects.get(id = object_id)
            if vol.vol_fstype == 'iscsi':
                diskdev = u'/dev/' + vol.vol_name[6:]
                ist = iSCSITargetExtent.objects.get(iscsi_target_extent_path = diskdev)
                ist.delete()
	return delete_object(
		request = request,
		model = storage_name_model_map[model_name],
		post_delete_redirect = '/storage/',
		object_id = object_id, )

@login_required
def generic_update(request, object_id, model_name):
        model_name_to_model_and_form_map = {
		'disk':	( Disk, DiskFormPartial ),
	}
	model, form_class = model_name_to_model_and_form_map[model_name]
	return update_object(
		request = request,
		model = model, form_class = form_class,
		post_save_redirect = '/storage/',
		object_id = object_id, )
