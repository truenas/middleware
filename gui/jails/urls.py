# Copyright 2013 iXsystems, Inc.
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

from .views import (
    jails_home, jailsconfiguration, jail_edit, jail_delete,
    jail_storage_add, jail_export, jail_import, jail_start, jail_stop,
    jail_restart, jail_progress, jail_linuxprogress, jail_info,
    jail_template_info, jail_template_create, jail_template_edit,
    jail_template_delete, jailsconfiguration_info,
    jailsconfiguration_network_info,
)

urlpatterns = [
    'freenasUI.jails.views',
    url(r'^home/$', jails_home, name="jails_home"),
    url(r'^configuration/$', jailsconfiguration, name="jailsconfiguration"),
    url(r'^edit/(?P<id>\d+)$', jail_edit, name="jail_edit"),
    url(r'^delete/(?P<id>\d+)$', jail_delete, name="jail_delete"),
    url(r'^storage_add/(?P<jail_id>\d+)$', jail_storage_add, name="jail_storage_add"),
    url(r'^export/(?P<id>\d+)$', jail_export, name="jail_export"),
    url(r'^import/$', jail_import, name="jail_import"),
    url(r'^start/(?P<id>\d+)$', jail_start, name="jail_start"),
    url(r'^stop/(?P<id>\d+)$', jail_stop, name="jail_stop"),
    url(r'^restart/(?P<id>\d+)$', jail_restart, name="jail_restart"),
    url(r'^progress/$', jail_progress, name="jail_progress"),
    url(r'^linuxprogress/$', jail_linuxprogress, name="jail_linuxprogress"),
    url(r'^jail/info/(?P<id>\d+)/$', jail_info, name="jail_info"),
    url(r'^template/info/(?P<name>.+)/$', jail_template_info, name="jail_template_info"),
    url(r'^template/create/$', jail_template_create, name="jail_template_create"),
    url(r'^template/edit/(?P<id>.+)/$', jail_template_edit, name="jail_template_edit"),
    url(r'^template/delete/(?P<id>.+)/$', jail_template_delete, name="jail_template_delete"),
    url(r'^jailsconfiguration/info/$', jailsconfiguration_info, name="jailsconfiguration_info"),
    url(r'^jailsconfiguration/network/info/$', jailsconfiguration_network_info, name="jailsconfiguration_network_info"),
]
