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

from freenasUI.sharing.forms import * 
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
from django.views.generic.create_update import update_object, delete_object
from freenasUI.middleware.notifier import notifier
import os, commands


@login_required
def sharing(request, sharetype = None):
    if sharetype != None:
        focus_form = sharetype
    else:
        focus_form = 'cifs'
    cifs = CIFS_ShareForm(request.POST)
    afp = AFP_ShareForm(request.POST)
    nfs = NFS_ShareForm(request.POST)
    if request.method == 'POST':
        if sharetype == 'cifs':
            cifs = CIFS_ShareForm(request.POST)
            if cifs.is_valid():
                cifs.save()
        elif sharetype == 'afp':
            afp = AFP_ShareForm(request.POST)
            if afp.is_valid():
                afp.save()
        elif sharetype == 'nfs':
            nfs = NFS_ShareForm(request.POST)
            if nfs.is_valid():
                nfs.save()
        else:
            raise Http404() # TODO: Should be something better
        return HttpResponseRedirect('/sharing' + '/global/' + sharetype)
    else:
        cifs_share_list = CIFS_Share.objects.select_related().all()
        afp_share_list = AFP_Share.objects.order_by("-id").values()
        nfs_share_list = NFS_Share.objects.select_related().all()
        cifs = CIFS_ShareForm()
        afp = AFP_ShareForm()
        nfs = NFS_ShareForm()
    variables = RequestContext(request, {
        'focused_tab' : 'sharing',
        'cifs_share_list': cifs_share_list,
        'afp_share_list': afp_share_list,
        'nfs_share_list': nfs_share_list,
        'cifs': cifs,
        'afp': afp,
        'nfs': nfs,
        'focus_form': focus_form,
        })
    return render_to_response('sharing/index.html', variables)

@login_required
def home(request):

    variables = RequestContext(request, {
    'focused_tab' : 'sharing',
    })
    return render_to_response('sharing/index2.html', variables)

@login_required
def windows(request):

    cifs_share_list = CIFS_Share.objects.select_related().all()

    variables = RequestContext(request, {
        'cifs_share_list': cifs_share_list,
    })
    return render_to_response('sharing/windows.html', variables)

@login_required
def apple(request):

    afp_share_list = AFP_Share.objects.order_by("-id").values()

    variables = RequestContext(request, {
    'afp_share_list': afp_share_list,
    })
    return render_to_response('sharing/apple.html', variables)

@login_required
def unix(request):

    nfs_share_list = NFS_Share.objects.select_related().all()

    variables = RequestContext(request, {
    'nfs_share_list': nfs_share_list,
    })
    return render_to_response('sharing/unix.html', variables)

@login_required
def generic_delete(request, object_id, sharetype):
    sharing_model_map = {
        'cifs':   CIFS_Share,
        'afp':   AFP_Share,
        'nfs':   NFS_Share,
    }
    return delete_object(
        request = request,
        model = sharing_model_map[sharetype],
        post_delete_redirect = '/sharing/' + sharetype + '/view/',
        object_id = object_id, )
    notifier().reload(sharetype)
    return retval

@login_required
def generic_update(request, object_id, sharetype):
    sharetype2form = {
            'cifs':   ( CIFS_Share, CIFS_ShareForm ),
            'afp':   ( AFP_Share, AFP_ShareForm ),
            'nfs':   ( NFS_Share, NFS_ShareForm ),
            } 
    model, form_class = sharetype2form[sharetype]
    return update_object(
        request = request,
        model = model, form_class = form_class,
        object_id = object_id, 
        post_save_redirect = '/sharing/' + sharetype + '/view/',
        )
    notifier().reload(sharetype)
    return retval
