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

from django.conf.urls.defaults import patterns, url

# Active FreeNAS URLs

urlpatterns = patterns('services.views',
    url(r'^home/$', 'home', name="services_home"),
    url(r'^iscsi/$', 'iscsi', name="services_iscsi"),
    url(r'^iscsi/targets/$', 'iscsi_targets', name="services_iscsi_targets"),
    url(r'^iscsi/assoc-targets/$', 'iscsi_assoctargets', name="services_iscsi_assoctargets"),
    url(r'^iscsi/extents/$', 'iscsi_extents', name="services_iscsi_extents"),
    url(r'^iscsi/dextents/$', 'iscsi_dextents', name="services_iscsi_dextents"),
    url(r'^iscsi/auth/$', 'iscsi_auth', name="services_iscsi_auth"),
    url(r'^iscsi/auth-ini/$', 'iscsi_authini', name="services_iscsi_authini"),
    url(r'^iscsi/portals/$', 'iscsi_portals', name="services_iscsi_portals"),
    url(r'toggle/(?P<formname>\w+)/.*$', 'servicesToggleView', name="services_toggle"),
    )
