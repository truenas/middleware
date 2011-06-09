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

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render_to_response, render
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.contrib.auth.views import login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm

from freenasUI.account import forms
from freenasUI.account import models

def home(request):
    focus_form = request.GET.get('tab', 'passform')
    return render(request, 'account/index.html', {
        'focus_form': focus_form,
    })

def bsduser(request):

    bsduser_list = models.bsdUsers.objects.order_by("id").select_related().filter(bsdusr_builtin=False)
    bsduser_list_builtin = models.bsdUsers.objects.order_by("id").select_related().filter(bsdusr_builtin=True)

    return render(request, 'account/bsdusers.html', {
        'bsduser_list': bsduser_list,
        'bsduser_list_builtin': bsduser_list_builtin,
    })

def bsdgroup(request):

    bsdgroup_list = models.bsdGroups.objects.order_by("id").filter(bsdgrp_builtin=False)
    bsdgroup_list_builtin = models.bsdGroups.objects.order_by("id").filter(bsdgrp_builtin=True)

    return render_to_response('account/bsdgroups.html', {
        'bsdgroup_list': bsdgroup_list,
        'bsdgroup_list_builtin': bsdgroup_list_builtin,
    })

def password_change(request):

    extra_context = {}
    password_change_form=forms.PasswordChangeForm
    passform = password_change_form(user=request.user)

    if request.method == 'POST':
        passform = password_change_form(user=request.user, data=request.POST)
        if passform.is_valid():
            passform.save()
            passform = password_change_form(user=request.user)
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Password successfully updated.")}), mimetype="application/json")

    extra_context.update({ 'passform' : passform, })
    return render(request, 'account/passform.html', extra_context)

def user_change(request):

    extra_context = {}
    changeform = forms.UserChangeForm(instance=request.user)

    if request.method == 'POST':
        changeform = forms.UserChangeForm(instance=request.user, data=request.POST)
        if changeform.is_valid():
            changeform.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Admin user successfully updated.")}), mimetype="application/json")

    extra_context.update({ 'changeform' : changeform, })
    return render(request, 'account/changeform.html', extra_context)

def group2user_update(request, object_id):
    if request.method == 'POST':
        f = forms.bsdGroupToUserForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Users successfully updated.")}), mimetype="application/json")
    else:
        f = forms.bsdGroupToUserForm(groupid=object_id)
    return render(request, 'account/bsdgroup2user_form.html', {
        'url': reverse('account_bsdgroup_members', kwargs={'object_id':object_id}),
        'form' : f,
    })

def user2group_update(request, object_id):
    if request.method == 'POST':
        f = forms.bsdUserToGroupForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return HttpResponse(simplejson.dumps({"error": False, "message": _("Groups successfully updated.")}), mimetype="application/json")
    else:
        f = forms.bsdUserToGroupForm(userid=object_id)
    return render(request, 'account/bsdgroup2user_form.html', {
        'url': reverse('account_bsduser_groups', kwargs={'object_id':object_id}),
        'form' : f,
    })

def json_users(request, exclude=None):

    from common.freenasldap import FreeNAS_Users
    query = request.GET.get("q", None)

    json = {
        'identifier': 'id',
        'label': 'name',
        'items': [],
    }

    if exclude:
        exclude = exclude.split(',')
    else:
        exclude = []
    idx = 1
    for user in FreeNAS_Users():
        if idx > 50:
            break
        if (query == None or user.bsdusr_username.startswith(query)) and \
          user.bsdusr_username not in exclude:
            json['items'].append({
                'id': user.bsdusr_username,
                'name': user.bsdusr_username,
                'label': user.bsdusr_username,
            })
            idx += 1
    return HttpResponse(simplejson.dumps(json, indent=3))

def json_groups(request):

    from common.freenasldap import FreeNAS_Groups
    query = request.GET.get("q", None)

    json = {
        'identifier': 'id',
        'label': 'name',
        'items': [],
    }

    idx = 1
    for grp in FreeNAS_Groups():
        if idx > 50:
            break
        if query == None or grp.bsdgrp_group.startswith(query):
            json['items'].append({
                'id': grp.bsdgrp_group,
                'name': grp.bsdgrp_group,
                'label': grp.bsdgrp_group,
            })
            idx += 1
    return HttpResponse(simplejson.dumps(json, indent=3))

"""
Wrapper to login to do not allow login and redirect to
shutdown, reboot or logout pages,
instead redirect to /
"""
def login_wrapper(request, template_name='registration/login.html',
          redirect_field_name=REDIRECT_FIELD_NAME,
          authentication_form=AuthenticationForm,
          current_app=None, extra_context=None):
    response = login(request, template_name='registration/login.html',
          redirect_field_name=redirect_field_name,
          authentication_form=authentication_form,
          current_app=current_app, extra_context=extra_context)
    if response.status_code in (301, 302) and response._headers.get('location', ('',''))[1] in (
            reverse('system_reboot'), reverse('system_shutdown'), reverse('account_logout')
            ):
        response._headers['location'] = ('Location', '/')
    return response
