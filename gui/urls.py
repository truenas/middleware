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
    (r'^freenas/network/$', NetworkView),
    (r'^freenas/network/staticroutes/(?P<staticrouteid>\d)$', staticroute_detail), # detail
    (r'^freenas/network/staticroutes/delete/(?P<object_id>\d)/$',
        'django.views.generic.create_update.delete_object', 
        dict(model = networkStaticRoute, post_delete_redirect = '/freenas/network/staticroutes/'),), 
    (r'^freenas/disk/management/$', DiskView), 
    (r'^freenas/disk/management/disks/(?P<diskid>\d)$', disk_detail), # detail
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
    (r'^freenas/shares/*$', SharesView),
    (r'^freenas/services/*$', ServicesView),
    (r'^freenas/status/processes/*$', statusProcessesView),
    (r'^freenas/access/$', AccessView), 
# Not sure why I need the this entry, but the last one works for James..
    (r'^dojango/(?P<path>.*)$',
        'django.views.static.serve',
        {'document_root': '/usr/local/www/freenasUI/dojango'}),
    (r'^dojango/', include('dojango.urls')),
    )
