#+
# Copyright 2010 iXsystems, Inc.
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
import os

from django.conf.urls import include, patterns, url
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.static import serve
from django.conf import settings
from django.template.loader import add_to_builtins

from freenasUI import freeadmin
from freenasUI.api import v1_api
from freenasUI.api.resources import SnapshotResource
from freenasUI.freeadmin.site import site
from freenasUI.freeadmin.middleware import public
from freenasUI.freeadmin.navtree import navtree

handler500 = 'freenasUI.freeadmin.views.server_error'
handler404 = 'freenasUI.freeadmin.views.page_not_found'

v1_api.register(SnapshotResource())

navtree.prepare_modelforms()
freeadmin.autodiscover()

add_to_builtins('django.templatetags.i18n')

urlpatterns = patterns('',
    url('^$', site.adminInterface, name="index"),
    (r'^reporting/graphs/(?P<path>.*)',
        public(serve),
        {'document_root': '/var/db/graphs/'}),
    (r'^media/(?P<path>.*)',
        public(serve),
        {'document_root': settings.MEDIA_ROOT}),
    (r'^static/(?P<path>.*)',
        public(serve),
        {'document_root': os.path.join(settings.HERE, "freeadmin/static")}),
    (r'^dojango/dojo-media/release/[^/]+/(?P<path>.*)$',
        public(serve),
        {'document_root': '/usr/local/www/dojo'}),
    (r'^account/', include('freenasUI.account.urls')),
    (r'^admin/', include(site.urls)),
    url(r'^api/', include(v1_api.urls)),
    (r'^jails/', include('freenasUI.jails.urls')),
    (r'^jsi18n/', 'django.views.i18n.javascript_catalog'),
    (r'^network/', include('freenasUI.network.urls')),
    (r'^plugins/', include('freenasUI.plugins.urls')),
    (r'^reporting/', include('freenasUI.reporting.urls')),
    (r'^services/', include('freenasUI.services.urls')),
    (r'^sharing/', include('freenasUI.sharing.urls')),
    (r'^storage/', include('freenasUI.storage.urls')),
    (r'^support/', include('freenasUI.support.urls')),
    (r'^system/', include('freenasUI.system.urls')),
)

urlpatterns += staticfiles_urlpatterns()
