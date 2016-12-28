# Copyright 2011 iXsystems, Inc.
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

from django.conf.urls import url

from jsonrpc import jsonrpc_site
import freenasUI.plugins.views

from .views import (
    home, plugins, install_available, upload, upload_nojail, upload_progress,
    install_progress, plugin_edit, plugin_info, plugin_available_icon,
    plugin_installed_icon, plugin_update, update_progress, plugin_fcgi_client,
)

urlpatterns = [
    url(r'^plugin/home/$', home, name="plugins_home"),
    url(r'^plugin/plugins/$', plugins, name="plugins_plugins"),
    url(r'^plugin/install/(?P<oid>[0-9a-f]{1,64})/$', install_available, name="plugins_install_available"),
    url(r'^plugin/upload/(?P<jail_id>\d+)/$', upload, name="plugins_upload"),
    url(r'^plugin/upload/$', upload_nojail, name="plugins_upload_nojail"),
    url(r'^plugin/upload/progress/$', upload_progress, name="plugins_upload_progress"),
    url(r'^plugin/install/progress/$', install_progress, name="plugins_install_progress"),
    url(r'^plugin/edit/(?P<plugin_id>\d+)/$', plugin_edit, name="plugin_edit"),
    url(r'^plugin/info/(?P<plugin_id>\d+)/$', plugin_info, name="plugin_info"),
    url(r'^plugin/available/icon/(?P<oid>[0-9a-f]{1,64})/$', plugin_available_icon, name="plugin_available_icon"),
    url(r'^plugin/installed/icon/(?P<plugin_name>[^/]+)/(?P<oid>[0-9a-f]{1,64})/$', plugin_installed_icon, name="plugin_installed_icon"),
    url(r'^plugin/update/(?P<oid>[0-9a-f]{1,64})/$', plugin_update, name="plugin_update"),
    url(r'^plugin/update/progress/$', update_progress, name="plugins_update_progress"),
    url(r'^json-rpc/v1/', jsonrpc_site.dispatch, name="plugins_jsonrpc_v1"),
    url(r'^(?P<name>[^/]+)/(?P<oid>\d+)/(?P<path>.+)$', plugin_fcgi_client, name="plugin_fcgi_client"),
]
