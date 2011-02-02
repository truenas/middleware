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

from django.conf.urls.defaults import *
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import password_change, password_change_done
from freenasUI.account.views import *

# Active FreeNAS URLs

urlpatterns = patterns('',
    (r'^$', bsdUsersView), 
    (r'admin/(?P<objtype>\w+)/$', bsdUsersView),
    (r'^(?P<objtype>\w+)/add/$', bsdUsersView),
    (r'(?P<objtype>\w+)/delete/(?P<object_id>\d+)/$', usergroup_delete),
    (r'bsdpasswd/edit/(?P<object_id>\d+)/$', password_update),
    (r'bsdgroup/members/(?P<object_id>\d+)/$', group2user_update),
    (r'bsduser/auxgroup/(?P<object_id>\d+)/$', user2group_update),
    (r'(?P<objtype>\w+)/edit/(?P<object_id>\d+)/$', generic_update),
    (r'^password_change/$', password_change),
    (r'^password_change/done/$', password_change_done, 
        {'template_name': 'registration/password_change_done.html'}),
    (r'^login/$', 'django.contrib.auth.views.login',
        {'template_name': 'registration/login.html'}),
    (r'^logout/$', 
        'django.contrib.auth.views.logout',
        {'template_name': 'registration/logout.html'}, 'auth_logout'),
    )
