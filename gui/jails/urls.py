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

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('freenasUI.jails.views',
    url(r'^home/$', 'jails_home', name="jails_home"),
    url(r'^auto/(?P<id>\d+)$', 'jail_auto', name="jail_auto"),
    url(r'^checkup/(?P<id>\d+)$', 'jail_checkup', name="jail_checkup"),
    url(r'^detals/(?P<id>\d+)$', 'jail_details', name="jail_details"),
    url(r'^export/(?P<id>\d+)$', 'jail_export', name="jail_export"),
    url(r'^import/(?P<id>\d+)$', 'jail_import', name="jail_import"),
    url(r'^options/(?P<id>\d+)$', 'jail_options', name="jail_options"),
    url(r'^pkgs/(?P<id>\d+)$', 'jail_pkgs', name="jail_pkgs"),
    url(r'^pbis/(?P<id>\d+)$', 'jail_pbis', name="jail_pbis"),
    url(r'^start/(?P<id>\d+)$', 'jail_start', name="jail_start"),
    url(r'^stop/(?P<id>\d+)$', 'jail_stop', name="jail_stop"),
    url(r'^zfsmksnap/(?P<id>\d+)$', 'jail_zfsmksnap', name="jail_zfsmksnap"),
    url(r'^zfslistclone/(?P<id>\d+)$', 'jail_zfslistclone', name="jail_zfslistclone"),
    url(r'^zfslistsnap/(?P<id>\d+)$', 'jail_zfslistsnap', name="jail_zfslistsnap"),
    url(r'^zfsclonesnap/(?P<id>\d+)$', 'jail_zfsclonesnap', name="jail_zfsclonesnap"),
    url(r'^zfscronsnap/(?P<id>\d+)$', 'jail_zfscronsnap', name="jail_zfscronsnap"),
    url(r'^zfsrevertsnap/(?P<id>\d+)$', 'jail_zfsrevertsnap', name="jail_zfsrevertsnap"),
    url(r'^zfsrmclonesnap/(?P<id>\d+)$', 'jail_zfsrmclonesnap', name="jail_zfsrmclonesnap"),
    url(r'^zfsrmsnap/(?P<id>\d+)$', 'jail_zfsrmsnap', name="jail_zfsrmsnap"),
    )

