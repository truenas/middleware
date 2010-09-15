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
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import password_change, password_change_done
from django.views.generic.simple import direct_to_template
from django.views.generic import list_detail
from freenasUI.freenas.models import *
from freenasUI.freenas.models import Disk
from freenasUI.freenas.views import *
import os, commands

#import django_nav
#django_nav.autodiscover()
#admin.autodiscover()

# Active FreeNAS URLs

urlpatterns = patterns('',
    (r'^password_change/$', password_change, 
        {'template_name': 'registration/password_change_form.html'}),
    (r'^password_change/done/$', password_change_done, 
        {'template_name': 'registration/password_change_done.html'}),
    (r'^media/(?P<path>.*)',
        'django.views.static.serve', 
        {'document_root': '/usr/local/www/freenasUI/media'}),
    (r'^freenas/media/(?P<path>.*)$',
        'django.views.static.serve', 
        {'document_root': '/usr/local/www/freenasUI/media'}),
    (r'^/*$', index),
    (r'^freenas/login/*$', 'django.contrib.auth.views.login',
        {'template_name': 'registration/login.html'}),
    (r'^freenas/logout/$', 
        'django.contrib.auth.views.logout',
        {'template_name': 'registration/logout.html'}, 'auth_logout'),
    (r'^freenas/system/reboot/$', systemReboot),
    (r'^freenas/system/shutdown/$', systemShutdown),
    (r'^freenas/system/general/setup/$', systemGeneralSetupView),
    (r'^freenas/system/general/password/$', systemGeneralPasswordView),
    (r'^freenas/system/advanced/$', systemAdvancedView),
    (r'^freenas/system/advanced/email/$', systemAdvancedEmailView),
    (r'^freenas/system/advanced/proxy/$', systemAdvancedProxyView),
    (r'^freenas/system/advanced/swap/$', systemAdvancedSwapView),
    (r'^freenas/system/advanced/commandscripts/add', CommandScriptsView),
    (r'^freenas/system/advanced/commandscripts/$', systemAdvancedCommandScriptsView),
    (r'^freenas/system/advanced/cronjobs/$', systemAdvancedCronView),
    (r'^freenas/system/advanced/cronjobs/add/$', cronjobView),
    (r'^freenas/system/advanced/rcconf/$', rcconfView),
    (r'^freenas/system/advanced/rcconf/edit/$', systemAdvancedRCconfView),
    (r'^freenas/system/advanced/sysctlconf/$', systemAdvancedSYSCTLconfView),
    (r'^freenas/system/advanced/sysctlconf/add/$', sysctlMIBView),
    (r'^freenas/network/interfaces/$', networkInterfaceMGMTView),
    (r'^freenas/network/vlan/add/$', networkVLANView),
    (r'^freenas/network/vlan/$', networkInterfaceMGMTvlanView),
    (r'^freenas/network/lagg/add/$', networkLAGGView),
    (r'^freenas/network/lagg/$', networkInterfaceMGMTlaggView),
    (r'^freenas/network/hosts/$', networkHostsView),
    (r'^freenas/network/staticroutes/add/$', staticroutes_add_wrapper),
    (r'^freenas/network/staticroutes/$', staticroutes_list),
    (r'^freenas/network/staticroutes/(?P<staticrouteid>\d)$', staticroute_detail), # detail
    (r'^freenas/network/staticroutes/delete/(?P<object_id>\d)/$',
        'django.views.generic.create_update.delete_object', 
        dict(model = networkStaticRoute, post_delete_redirect = '/freenas/network/staticroutes/'),), 
    (r'^freenas/disk/management/disks/add/$', disk_add_wrapper), # add
    (r'^freenas/disk/management/disks/(?P<diskid>\d)$', disk_detail), # detail
    ('^freenas/disk/management/disks/$', disk_list), # list
    (r'^freenas/disk/management/disks/delete/(?P<object_id>\d)/$',
        'django.views.generic.create_update.delete_object', # delete
        dict(model = Disk, post_delete_redirect = '/freenas/disk/management/disks/'),), 
    (r'^freenas/disk/management/groups/add/$', diskgroup_add_wrapper),
    (r'^freenas/disk/management/groups/(?P<diskgroupid>\d)$', diskgroup_detail),
    (r'^freenas/disk/management/groups/*$', diskgroup_list),
    (r'^freenas/disk/management/groups/delete/(?P<object_id>\d)/$',
        'django.views.generic.create_update.delete_object', 
        dict(model = DiskGroup, post_delete_redirect = '/freenas/disk/management/groups/'),), 
    (r'^freenas/disk/management/volumes/create/$', volume_create_wrapper), 
    (r'^freenas/disk/management/volumes/(?P<volumeid>\d)$', volume_detail),
    (r'^freenas/disk/management/volumes/$', volume_list),
    (r'^freenas/disk/management/volumes/delete/(?P<object_id>\d)/$',
        'django.views.generic.create_update.delete_object', 
        dict(model = Volume, post_delete_redirect = '/freenas/disk/management/volumes/'),), 
    (r'^freenas/services/cifs/$', servicesCIFSView),
    (r'^freenas/services/cifs/shares/add/$', shareCIFSView),
    (r'^freenas/services/cifs/shares/$', servicesCIFSshareView),
    (r'^freenas/services/ftp/$', servicesFTPView),
    (r'^freenas/services/tftp/$', servicesTFTPView),
    (r'^freenas/services/ssh/$', servicesSSHView),
    (r'^freenas/services/nfs/$', servicesNFSView),
    (r'^freenas/services/nfs/shares/add/$', shareNFSView),
    (r'^freenas/services/nfs/shares/$', servicesNFSshareView),
    (r'^freenas/services/afp/$', servicesAFPView),
    (r'^freenas/services/afp/shares/add/$', shareAFPView),
    (r'^freenas/services/afp/shares/$', servicesAFPshareView),
    (r'^freenas/services/rsync/clientjobs/$', clientrsyncjobView),
    (r'^freenas/services/rsync/localjobs/$', localrsyncjobView),
    (r'^freenas/services/rsync/$', servicesRSYNCView),
    (r'^freenas/services/unison/$', servicesUnisonView),
    (r'^freenas/services/iscsi/$', servicesiSCSITargetView),
    (r'^freenas/services/dyndns/$', servicesDynamicDNSView),
    (r'^freenas/services/snmp/$', servicesSNMPView),
    (r'^freenas/services/ups/$', servicesUPSView),
    (r'^freenas/services/webserver/$', servicesWebserverView),
    (r'^freenas/services/bittorrent/$', servicesBitTorrentView),
    (r'^freenas/status/processes/*$', statusProcessesView),
    (r'^freenas/access/$',
            login_required(direct_to_template),
            {'template': 'freenas/access/index.html'}),
    (r'^freenas/access/active_directory/$', accessActiveDirectoryView),
    (r'^freenas/access/ldap/$', accessLDAPView),
    (r'^dojango/', include('dojango.urls')),
    )
