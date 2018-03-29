#
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
import logging

from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm

from freenasUI.account import forms, models
from freenasUI.common.system import get_sw_login_version, get_sw_name, get_sw_year, get_sw_version
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp

log = logging.getLogger('account.views')


def home(request):

    view = appPool.hook_app_index('account', request)
    view = [_f for _f in view if _f]
    if view:
        return view[0]

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


class ExtendedAuthForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        if request is not None:
            initial = kwargs.get('initial', {})
            initial_default = {}
            initial_default.update(initial)
            kwargs['initial'] = initial_default
        super(ExtendedAuthForm, self).__init__(request, *args, **kwargs)


def login_wrapper(
    request,
    template_name='registration/login.html',
    redirect_field_name=REDIRECT_FIELD_NAME,
    authentication_form=ExtendedAuthForm,
    current_app=None, extra_context=None,
):
    """
    Wrapper to login to do not allow login and redirect to
    shutdown, reboot or logout pages,
    instead redirect to /
    """

    auth_token = request.GET.get('auth_token')
    if auth_token:
        user = authenticate(auth_token=auth_token)
        if user:
            auth_login(request, user, 'freenasUI.middleware.auth.AuthTokenBackend')

    # Overload hook_app_index to shortcut passive node
    # Doing that in another layer will use too many reasources
    view = appPool.hook_app_index('account_login', request)
    view = [_f for _f in view if _f]
    if view:
        return view[0]

    if extra_context is None:
        extra_context = {}
    extra_context.update({
        'sw_login_version': get_sw_login_version(),
        'sw_version_footer': get_sw_version(strip_build_num=True).split('-', 1)[-1],
        'sw_name': get_sw_name(),
        'sw_year': get_sw_year(),
    })
    if not models.bsdUsers.has_root_password():
        authentication_form = forms.NewPasswordForm
        extra_context.update({
            'reset_password': True,
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
        response._headers['location'] = ('Location', '/legacy/')
    elif request.user.is_authenticated:
        return HttpResponseRedirect('/legacy/')
    return response
