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
from freenasUI.storage.models import *
from freenasUI.storage.views import *
import os, commands

#import django_nav
#django_nav.autodiscover()
#admin.autodiscover()

# Active FreeNAS URLs

urlpatterns = patterns('',
    (r'^$', storage), 
    (r'save/(?P<objtype>\w+)/$', storage),
    (r'^disks/delete/(?P<object_id>\d+)/$',
        'django.views.generic.create_update.delete_object', 
        dict(model = Disk, post_delete_redirect = '/storage/'),), 
    (r'^(?P<model>\w+)/delete/(?P<object_id>\d+)/$',
        'django.views.generic.create_update.delete_object', 
        dict(post_delete_redirect = '/storage/'),), 
    (r'^(?P<model_url>\d+)/(?P<object_id>\d+)$', generic_detail), # detail based on URL
    )

# Once the names are normalized disks/Disk diskgroup/DiskGroup volume/Volume

# (r'(?<model>\w+)/delete/(?<object_idd>\d+)/$,
#  'django.views.generic.create_update.delete_object', 
#  dict(post_delete_redirect = '/storage/'),), 
