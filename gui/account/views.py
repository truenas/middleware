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
import json
import logging

from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.contrib.auth.views import login
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.forms import AuthenticationForm

from freenasUI.account import forms, models
from freenasUI.common.freenascache import (
    FLAGS_CACHE_READ_USER, FLAGS_CACHE_WRITE_USER, FLAGS_CACHE_READ_GROUP,
    FLAGS_CACHE_WRITE_GROUP
)
from freenasUI.common.freenasldap import (
    FLAGS_DBINIT,
    FreeNAS_ActiveDirectory_Groups,
    FreeNAS_ActiveDirectory_Users,
    FreeNAS_LDAP_Groups,
    FreeNAS_LDAP_Users,
)
from freenasUI.common.freenasnis import (
    FreeNAS_NIS_Groups,
    FreeNAS_NIS_Users,
)
from freenasUI.common.freenasusers import FreeNAS_Users, FreeNAS_Groups
from freenasUI.common.system import get_sw_login_version, get_sw_name
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp

log = logging.getLogger('account.views')


def home(request):

    view = appPool.hook_app_index('account', request)
    view = filter(None, view)
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

    json_user = {
        'identifier': 'id',
        'label': 'name',
        'items': [],
    }

    if exclude:
        exclude = exclude.split(',')
    else:
        exclude = []
    idx = 1
    curr_users = []
    for user in FreeNAS_Users(
        flags=FLAGS_DBINIT | FLAGS_CACHE_READ_USER | FLAGS_CACHE_WRITE_USER
    ):
        if idx > 50:
            break
        if (
            (query is None or user.pw_name.startswith(query.encode('utf8'))) and
            user.pw_name not in exclude and user.pw_name not in curr_users
        ):
            json_user['items'].append({
                'id': user.pw_name,
                'name': user.pw_name,
                'label': user.pw_name,
            })
            curr_users.append(user.pw_name)
            idx += 1

    # Show users for the directory service provided in the wizard
    wizard_ds = request.session.get('wizard_ds')
    if request.GET.get('wizard') == '1' and wizard_ds:
        if wizard_ds.get('ds_type') == 'ad':
            users = FreeNAS_ActiveDirectory_Users(
                domainname=wizard_ds.get('ds_ad_domainname'),
                bindname=wizard_ds.get('ds_ad_bindname'),
                bindpw=wizard_ds.get('ds_ad_bindpw'),
                flags=FLAGS_DBINIT,
            )
        elif wizard_ds.get('ds_type') == 'ldap':
            users = FreeNAS_LDAP_Users(
                host=wizard_ds.get('ds_ldap_hostname'),
                basedn=wizard_ds.get('ds_ldap_basedn'),
                binddn=wizard_ds.get('ds_ldap_binddn'),
                bindpw=wizard_ds.get('ds_ldap_bindpw'),
                flags=FLAGS_DBINIT,
            )
        elif wizard_ds.get('ds_type') == 'nis':
            users = FreeNAS_NIS_Users(
                domain=wizard_ds.get('ds_nis_domain'),
                servers=wizard_ds.get('ds_nis_servers'),
                secure_mode=wizard_ds.get('ds_nis_secure_mode'),
                manycast=wizard_ds.get('ds_nis_manycast'),
                flags=FLAGS_DBINIT,
            )
        else:
            users = None

        if users is not None:
            idx = 1
            # FIXME: code duplication withe the block above
            for user in users._get_uncached_usernames():
                if idx > 50:
                    break
                if (
                    (query is None or user.startswith(query.encode('utf8'))) and
                    user not in exclude
                ):
                    json_user['items'].append({
                        'id': '%s_%s' % (
                            wizard_ds.get('ds_type'),
                            user,
                        ),
                        'name': user,
                        'label': user,
                    })
                    idx += 1

            del users

    return HttpResponse(
        json.dumps(json_user, indent=3),
        content_type='application/json',
    )


def json_groups(request):

    query = request.GET.get("q", None)

    json_group = {
        'identifier': 'id',
        'label': 'name',
        'items': [],
    }

    idx = 1
    curr_groups = []
    for grp in FreeNAS_Groups(
        flags=FLAGS_DBINIT | FLAGS_CACHE_READ_GROUP | FLAGS_CACHE_WRITE_GROUP
    ):
        if idx > 50:
            break
        if ((query is None or grp.gr_name.startswith(query.encode('utf8'))) and
            grp.gr_name not in curr_groups):
            json_group['items'].append({
                'id': grp.gr_name,
                'name': grp.gr_name,
                'label': grp.gr_name,
            })
            idx += 1
            curr_groups.append(grp.gr_name)

    # Show groups for the directory service provided in the wizard
    wizard_ds = request.session.get('wizard_ds')
    if request.GET.get('wizard') == '1' and wizard_ds:
        if wizard_ds.get('ds_type') == 'ad':
            groups = FreeNAS_ActiveDirectory_Groups(
                domainname=wizard_ds.get('ds_ad_domainname'),
                bindname=wizard_ds.get('ds_ad_bindname'),
                bindpw=wizard_ds.get('ds_ad_bindpw'),
                flags=FLAGS_DBINIT,
            )
        elif wizard_ds.get('ds_type') == 'ldap':
            groups = FreeNAS_LDAP_Groups(
                host=wizard_ds.get('ds_ldap_hostname'),
                basedn=wizard_ds.get('ds_ldap_basedn'),
                binddn=wizard_ds.get('ds_ldap_binddn'),
                bindpw=wizard_ds.get('ds_ldap_bindpw'),
                flags=FLAGS_DBINIT,
            )
        elif wizard_ds.get('ds_type') == 'nis':
            groups = FreeNAS_NIS_Groups(
                domain=wizard_ds.get('ds_nis_domain'),
                servers=wizard_ds.get('ds_nis_servers'),
                secure_mode=wizard_ds.get('ds_nis_secure_mode'),
                manycast=wizard_ds.get('ds_nis_manycast'),
                flags=FLAGS_DBINIT,
            )
        else:
            groups = None

        if groups is not None:
            idx = 1
            # FIXME: code duplication withe the block above
            for group in groups._get_uncached_groupnames():
                if idx > 50:
                    break
                if query is None or group.startswith(query.encode('utf8')):
                    json_group['items'].append({
                        'id': '%s_%s' % (
                            wizard_ds.get('ds_type'),
                            group,
                        ),
                        'name': group,
                        'label': group,
                    })
                    idx += 1

            del groups

    return HttpResponse(
        json.dumps(json_group, indent=3),
        content_type='application/json',
    )


class ExtendedAuthForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        if request is not None:
            initial = kwargs.get('initial', {})
            initial_default = {'username': 'root'}
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

    # Overload hook_app_index to shortcut passive node
    # Doing that in another layer will use too many reasources
    view = appPool.hook_app_index('account_login', request)
    view = filter(None, view)
    if view:
        return view[0]

    if extra_context is None:
        extra_context = {}
    extra_context.update({
        'sw_login_version': get_sw_login_version(),
        'sw_name': get_sw_name(),
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
        response._headers['location'] = ('Location', '/')
    elif request.user.is_authenticated():
        return HttpResponseRedirect('/')
    return response
