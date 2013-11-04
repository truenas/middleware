#+
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

from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import simplejson
from django.utils.translation import ugettext as _
from django.contrib.auth.views import login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm

from freenasUI.account import forms
from freenasUI.common.freenasldap import FLAGS_DBINIT
from freenasUI.common.freenascache import (
    FLAGS_CACHE_READ_USER, FLAGS_CACHE_WRITE_USER, FLAGS_CACHE_READ_GROUP,
    FLAGS_CACHE_WRITE_GROUP
)
from freenasUI.common.freenasusers import FreeNAS_Users, FreeNAS_Groups
from freenasUI.common.system import get_sw_login_version, get_sw_name
from freenasUI.freeadmin.views import JsonResp


def home(request):
    focus_form = request.GET.get('tab', 'passform')
    return render(request, 'account/index.html', {
        'focus_form': focus_form,
    })


def group2user_update(request, object_id):
    if request.method == 'POST':
        f = forms.bsdGroupToUserForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return JsonResp(request, message=_("Users successfully updated."))
    else:
        f = forms.bsdGroupToUserForm(groupid=object_id)
    return render(request, 'account/bsdgroup2user_form.html', {
        'url': reverse(
            'account_bsdgroup_members',
            kwargs={'object_id': object_id}
        ),
        'form': f,
    })


def user2group_update(request, object_id):
    if request.method == 'POST':
        f = forms.bsdUserToGroupForm(object_id, request.POST)
        if f.is_valid():
            f.save()
            return JsonResp(request, message=_("Groups successfully updated."))
    else:
        f = forms.bsdUserToGroupForm(userid=object_id)
    return render(request, 'account/bsdgroup2user_form.html', {
        'url': reverse(
            'account_bsduser_groups',
            kwargs={'object_id': object_id}
        ),
        'form': f,
    })


def json_users(request, exclude=None):

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
    for user in FreeNAS_Users(
        flags=FLAGS_DBINIT | FLAGS_CACHE_READ_USER | FLAGS_CACHE_WRITE_USER
    ):
        if idx > 50:
            break
        if (
            (query is None or user.pw_name.startswith(query)) and
            user.pw_name not in exclude
        ):
            json['items'].append({
                'id': user.pw_name,
                'name': user.pw_name,
                'label': user.pw_name,
            })
            idx += 1
    return HttpResponse(simplejson.dumps(json, indent=3))


def json_groups(request):

    query = request.GET.get("q", None)

    json = {
        'identifier': 'id',
        'label': 'name',
        'items': [],
    }

    idx = 1
    for grp in FreeNAS_Groups(
        flags=FLAGS_DBINIT | FLAGS_CACHE_READ_GROUP | FLAGS_CACHE_WRITE_GROUP
    ):
        if idx > 50:
            break
        if query is None or grp.gr_name.startswith(query):
            json['items'].append({
                'id': grp.gr_name,
                'name': grp.gr_name,
                'label': grp.gr_name,
            })
            idx += 1
    return HttpResponse(simplejson.dumps(json, indent=3))


def login_wrapper(
    request,
    template_name='registration/login.html',
    redirect_field_name=REDIRECT_FIELD_NAME,
    authentication_form=AuthenticationForm,
    current_app=None, extra_context={}
):
    """
    Wrapper to login to do not allow login and redirect to
    shutdown, reboot or logout pages,
    instead redirect to /
    """
    extra_context.update({
        'sw_login_version': get_sw_login_version(),
        'sw_name': get_sw_name(),
    })
    response = login(
        request,
        template_name='registration/login.html',
        redirect_field_name=redirect_field_name,
        authentication_form=authentication_form,
        current_app=current_app,
        extra_context=extra_context,
    )
    if response.status_code in (301, 302) and response._headers.get(
        'location', ('', '')
    )[1] in (
        reverse('system_reboot'),
        reverse('system_shutdown'),
        reverse('account_logout'),
    ):
        response._headers['location'] = ('Location', '/')
    elif request.user.is_authenticated():
        return HttpResponseRedirect('/')
    return response
