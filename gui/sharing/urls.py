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
from freenasUI.sharing.views import *
from freenasUI.sharing.models import *
import os, commands

urlpatterns = patterns('sharing.views',
    (r'^$', 'sharing'), 
    url(r'^home/$', 'home', name="sharing_home"), 
    (r'^global/(?P<sharetype>\w+)/$', 'sharing'),
    (r'(?P<sharetype>\w+)/view/$', 'sharing'),
    (r'^save/(?P<sharetype>\w+)/$', 'sharing'), 
    (r'(?P<sharetype>\w+)/edit/(?P<object_id>\d+)/$', 'generic_update'),
    (r'^(?P<sharetype>\w+)/delete/(?P<object_id>\d+)/$', 'generic_delete'),
    )
