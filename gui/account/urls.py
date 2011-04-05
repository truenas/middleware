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
from django.contrib.auth.views import password_change, password_change_done, login, logout

# Active FreeNAS URLs

urlpatterns = patterns('account.views',
    (r'^$', 'bsdUsersView'), 
    url(r'^home/$', 'home', name="account_home"), 
    url(r'^bsduser/$', 'bsduser', name="account_bsduser"), 
    url(r'^bsduser/(?P<object_id>\d+)/groups/$', 'user2group_update2', name="account_bsduser_groups"), 
    url(r'^bsdgroup/$', 'bsdgroup', name="account_bsdgroup"), 
    url(r'^bsdgroup/(?P<object_id>\d+)/members/$', 'group2user_update2', name="account_bsdgroup_members"), 
    url(r'^password_change2/$', 'password_change2', name="account_passform"),
    url(r'^user_change/$', 'user_change', name="account_changeform"),
    (r'admin/(?P<objtype>\w+)/$', 'bsdUsersView'),
    (r'^(?P<objtype>\w+)/add/$', 'bsdUsersView'),
    (r'(?P<objtype>\w+)/delete/(?P<object_id>\d+)/$', 'usergroup_delete'),
    (r'bsdpasswd/edit/(?P<object_id>\d+)/$', 'password_update'),
    (r'bsdgroup/members/(?P<object_id>\d+)/$', 'group2user_update'),
    (r'bsduser/auxgroup/(?P<object_id>\d+)/$', 'user2group_update'),
    (r'^password_change/$', password_change),
    (r'^password_change/done/$', password_change_done, 
        {'template_name': 'registration/password_change_done.html'}),
    (r'^login/$', login,
        {'template_name': 'registration/login.html'}),
    (r'^logout/$', 
        logout,
        {'template_name': 'registration/logout.html'}, 'auth_logout'),
    )
