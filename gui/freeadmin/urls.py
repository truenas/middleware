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
from django.contrib.auth.decorators import login_required

urlpatterns = patterns('freenasUI.freeadmin.views',
    url(r'^app-(?P<app>\w+)/(?P<model>\w+)/add/(?P<mf>.+?)?$', 'generic_model_add', name="freeadmin_model_add"),
    url(r'^app-(?P<app>\w+)/(?P<model>\w+)/edit/(?P<oid>\d+)/(?P<mf>.+?)?$', 'generic_model_edit', name="freeadmin_model_edit"),
    url(r'^app-(?P<app>\w+)/(?P<model>\w+)/delete/(?P<oid>\d+)/$', 'generic_model_delete', name="freeadmin_model_delete"),
    url(r'^app-(?P<app>\w+)/(?P<model>\w+)/$', 'generic_model_view', name="freeadmin_model_view"),
    url(r'^app-(?P<app>\w+)/(?P<model>\w+)/datagrid/$', 'generic_model_datagrid', name="freeadmin_model_datagrid"),
    url(r'^app-(?P<app>\w+)/(?P<model>\w+)/datagrid/json$', 'generic_model_datagrid_json', name="freeadmin_model_datagrid_json"),
    url(r'^menu\.json$', 'menu', name="freeadmin_menu"),
    (r'^interface/$', 'adminInterface'),
)
