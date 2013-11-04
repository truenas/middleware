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

from django.conf.urls import patterns, url
from django.contrib.auth.views import logout

from freenasUI.common.system import get_sw_name


urlpatterns = patterns(
    'freenasUI.account.views',
    url(r'^home/$', 'home', name="account_home"),
    url(r'^bsduser/json/$', 'json_users', name="account_bsduser_json"),
    url(r'^bsduser/json/(?P<exclude>.+)/$', 'json_users', name="account_bsduser_json"),
    url(r'^bsduser/(?P<object_id>\d+)/groups/$', 'user2group_update', name="account_bsduser_groups"),
    url(r'^bsdgroup/json/$', 'json_groups', name="account_bsdgroup_json"),
    url(r'^bsdgroup/(?P<object_id>\d+)/members/$', 'group2user_update', name="account_bsdgroup_members"),
    url(r'^login/$', 'login_wrapper', {'template_name': 'registration/login.html'}, name="account_login"),
    url(r'^logout/$', logout, {'template_name': 'registration/logout.html', 'extra_context': {'sw_name': get_sw_name()}}, name="account_logout"),
)
