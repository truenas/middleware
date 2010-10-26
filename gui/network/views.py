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

from freenasUI.network.forms import * 
from freenasUI.network.models import * 
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
from freenasUI.middleware.notifier import notifier
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


## Network Section

@login_required
def network(request, objtype = None):
    if request.method == 'POST':
        if objtype == 'configuration':
            gc = GlobalConfigurationForm(request.POST)
            gc.save()
        elif objtype == 'int':
            interfaces = InterfacesForm(request.POST)
            interfaces.save()
        elif objtype == 'vlan':
            vlan = VLANForm(request.POST)
            vlan.save()
        elif objtype == 'lagg':
            lagg = LAGGForm(request.POST)
            lagg.save()
        elif objtype == 'sr':
            staticroute = StaticRouteForm(request.POST)
            staticroute.save()
        else:
            raise Http404() 
        return HttpResponseRedirect('/network/')
    else:
        gc_config = GlobalConfiguration.objects.order_by("-id").values()[:1]
        int_list = Interfaces.objects.order_by("-id").values()
        gc = GlobalConfigurationForm(data = GlobalConfiguration.objects.order_by("-id").values()[0])
        interfaces = InterfacesForm()
        vlan = VLANForm()
        lagg = LAGGForm()
        staticroute = StaticRouteForm()
    variables = RequestContext(request, {
        'gc_config': gc_config,
        'gc': gc,
        'interfaces': interfaces,
        'int_list': int_list,
        'vlan': vlan,
        'lagg': lagg,
        'staticroute': staticroute,
    })
    return render_to_response('network/index.html', variables)
