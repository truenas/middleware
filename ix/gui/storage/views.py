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
from freenasUI.storage.forms import * 
from freenasUI.storage.models import * 
from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404
from django.views.generic.list_detail import object_detail, object_list
from django.views.generic.create_update import delete_object
from freenasUI.middleware.notifier import notifier
from django.core import serializers
import os, commands

def helperView(request, theForm, model, url):
    if request.method == 'POST':
        form = theForm(request.POST)
        if form.is_valid():
            form.save()
            if model.objects.count() > 3:
                stale_id = model.objects.order_by("-id")[3].id
                model.objects.filter(id__lte=stale_id).delete()
        else:
            # This is a debugging aid to raise exception when validation
            # is not passed.
            form.save()
    else:
        try:
            _entity = model.objects.order_by("-id").values()[0]
        except:
            # TODO: We throw an exception (which makes this try/except
            # meaningless) for now.  A future version will have the
            # ability to set up default values.
            raise
        form = theForm(data = _entity)
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response(url, variables)

def helperViewEm(request, theForm, model):
    data_saved = 0
    if request.method == 'POST':
        form = theForm(request.POST)
        if form.is_valid():
            # TODO: test if the data is the same as what is in the database?
            form.save()
            data_saved = 1
            if model.objects.count() > 3:
                stale_id = model.objects.order_by("-id")[3].id
                model.objects.filter(id__lte=stale_id).delete()
        else:
            pass
    else:
        try:
            _entity = model.objects.order_by("-id").values()[0]
        except:
            _entity = None
        form = theForm(data = _entity)
    return (data_saved, form)



## Disk section

@login_required
def storage(request, objtype = None, template_name = 'storage/index.html'):
    disk = DiskForm(request.POST)
    diskgroup = DiskGroupForm(request.POST)
    volume = VolumeForm(request.POST)
    mountpoint = MountPointForm(request.POST)
    if request.method == 'POST':
        if objtype == 'disk':
            disk.save()
        elif objtype == 'diskgroup':
            diskgroup.save()
        elif objtype == 'volume':
            volume.save()
        elif objtype == 'mountpoint':
            mountpoint.save()
        else:
            raise ValueError("Invalid Request")
        return HttpResponseRedirect('/storage/')
    else:
        disk = DiskForm()
        diskgroup = DiskGroupForm()
        volume = VolumeForm()
        mountpoint = MountPointForm()
        variables = RequestContext(request, {
            'disk': disk,
            'diskgroup': diskgroup,
            'volume': volume,
            'mountpoint': mountpoint,
            })
        return render_to_response('storage/index.html', variables)


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
def generic_detail(object_id, model_url):
    if model_url == "volume":
        return object_detail(
                object_id,
                queryset = Volume.objects.all(),
                )
    elif model_url == "diskgroup":
        return object_detail(
                object_id,
                queryset = DiskGroup.objects.all(),
                )
    elif model_url == "disk":
        return object_detail(
                object_id,
                queryset = Disk.objects.all(),
                )

@login_required
def generic_delete(request, object_id, model_name):
	storage_name_model_map = {
		'disks':	Disk,
		'groups':	DiskGroup,
		'volumes':	Volume,
	}
	return delete_object(
		request = request,
		model = storage_name_model_map[model_name],
		post_delete_redirect = '/storage/',
		object_id = object_id, )

