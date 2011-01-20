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

from freenasUI.account.forms import * 
from freenasUI.account.models import * 
from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import password_change_done
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404
from django.views.generic.list_detail import object_detail, object_list
from django.views.generic.create_update import update_object, delete_object
from freenasUI.middleware.notifier import notifier
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, PasswordChangeForm
from django.views.decorators.csrf import csrf_protect
import os, commands
from django.core.urlresolvers import reverse

@csrf_protect
@login_required
def bsdUsersView(request, objtype = None, post_change_redirect=None, password_change_form=PasswordChangeForm):
    if objtype != None:
        focus_form = objtype
    else:
        focus_form = 'bsduser'

    bsduser = bsdUserCreationForm()
    passform = password_change_form(user=request.user, data=request.GET)
    bsdgroup = bsdGroupsForm()
    bsduser_list = bsdUsers.objects.order_by("id").values()
    bsdgroup_list = bsdGroups.objects.order_by("id").values()

    #if post_change_redirect is None:
     #   post_change_redirect = reverse('django.contrib.auth.views.password_change_done')
    if request.method == 'POST':
        if objtype == 'passform':
            passform = password_change_form(user=request.user, data=request.POST)
            if passform.is_valid():
                passform.save()
        elif objtype == 'bsduser':
            bsduser = bsdUserCreationForm(request.POST)
            if bsduser.is_valid():
                bsduser.save()
        elif objtype == 'bsdgroup':
            bsdgroup = bsdGroupsForm(request.POST)
            if bsdgroup.is_valid():
                bsdgroup.save()
        else: 
            raise Http404()
        return HttpResponseRedirect('/account/' + objtype + '/add/')
    variables = RequestContext(request, {
        'focused_tab' : 'account',
        'passform': passform,
        'bsduser': bsduser,
        'bsdgroup': bsdgroup,
        'bsduser_list': bsduser_list,
        'bsdgroup_list': bsdgroup_list,
        'focus_form': focus_form,
    })
    return render_to_response('account/index.html', variables)

@login_required
def generic_delete(request, object_id, objtype):
    account_model_map = {
        'bsduser':   bsdUsers,
        'bsdgroup':   bsdGroups,
    }
    return delete_object(
        request = request,
        model = account_model_map[objtype],
        post_delete_redirect = '/account/',
        object_id = object_id, )

@login_required
def generic_update(request, object_id, objtype):
    objtype2form = {
            'bsduser':   ( bsdUsers, None ),
            'bsdgroup':   ( bsdGroups, None ),
            } 
    model, form_class = objtype2form[objtype]
    return update_object(
        request = request,
        model = model, form_class = form_class,
        object_id = object_id, 
        post_save_redirect = '/account/' + objtype + '/edit/' + object_id + '/',
        )

@login_required
def reboot(request):
    """ reboots the system """
    notifier().restart("system")
    return render_to_response('system/reboot.html')

@login_required
def shutdown(request):
    """ shuts down the system and powers off the system """
    notifier().stop("system")
    return render_to_response('system/shutdown.html')

