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

urlpatterns = patterns('freenasUI.system.views',
    url(r'^reboot/$', 'reboot', name="system_reboot"),
    url(r'^shutdown/$', 'shutdown', name="system_shutdown"),
    url(r'^reporting/$', 'reporting', name="system_reporting"),
    url(r'^settings2/$', 'settings', name="system_settings"),
    url(r'^advanced2/$', 'advanced', name="system_advanced"),
    url(r'^info/$', 'system_info', name="system_info"),
    url(r'^firmwizard/$', 'firmware_location', name='system_firmwizard'),
    url(r'^firmware2/$', 'firmware_upload', name="system_firmwareupload"),
    url(r'^firmwareloc/$', 'firmware_location', name="system_firmwarelocation"),
    url(r'^config/$', 'config', name='system_config'),
    url(r'^config/restore/$', 'config_restore', name='system_configrestore'),
    url(r'^config/save/$', 'config_save', name='system_configsave'),
    url(r'^config/upload/$', 'config_upload', name='system_configupload'),
    url(r'^config/upload/$', 'config_upload', name='system_configupload'),
    url(r'^varlogmessages/(?P<lines>\d+)?/?$', 'varlogmessages', name="system_messages"),
    url(r'^top/', 'top', name="system_top"),
    url(r'^test-mail/$', 'testmail', name="system_testmail"),
    )
