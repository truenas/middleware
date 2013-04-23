#+
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

from django.conf.urls import patterns, url

urlpatterns = patterns('freenasUI.jails.views',
    url(r'^home/$', 'jails_home', name="jails_home"),
    url(r'^configuration/$', 'jails_jailsconfiguration', name="jails_jailsconfiguration"),
    url(r'^edit/(?P<id>\d+)$', 'jail_edit', name="jail_edit"),
    url(r'^delete/(?P<id>\d+)$', 'jail_delete', name="jail_delete"),
    url(r'^mkdir/(?P<id>\d+)?$', 'jail_mkdir', name="jail_mkdir"),
    url(r'^storage_add/(?P<jail_id>\d+)$', 'jail_storage_add', name="jail_storage_add"),
    url(r'^storage_view/(?P<id>\d+)$', 'jail_storage_view', name="jail_storage_view"),
    url(r'^export/(?P<id>\d+)$', 'jail_export', name="jail_export"),
    url(r'^import/$', 'jail_import', name="jail_import"),
    url(r'^start/(?P<id>\d+)$', 'jail_start', name="jail_start"),
    url(r'^stop/(?P<id>\d+)$', 'jail_stop', name="jail_stop"),
    )

