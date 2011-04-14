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

from django.conf.urls.defaults import include, patterns
from freenasUI.freeadmin.views import adminInterface
from django.views.static import serve
from django.conf import settings

from freeadmin import navtree
from freeadmin.middleware import public
navtree.auto_generate()

urlpatterns = patterns('',
    ('^$', adminInterface),
    (r'^reporting/graphs/(?P<path>.*)',
        public(serve),
        {'document_root': '/var/db/graphs/'}),
    (r'^media/(?P<path>.*)',
        public(serve),
        {'document_root': settings.MEDIA_ROOT}),
    (r'^freenas/media/(?P<path>.*)$',
        public(serve),
        {'document_root': settings.MEDIA_ROOT}),
    (r'^dojango/(?P<path>.*)$',
        public(serve),
        {'document_root': settings.MEDIA_ROOT+'/../dojango/'}),
    (r'^dojangogrid/', include('dojango.urls')),
    (r'^admin/', include('freeadmin.urls')),
    (r'^account/', include('account.urls')),
    (r'^system/', include('system.urls')),
    (r'^network/', include('network.urls')),
    (r'^storage/', include('storage.urls')),
    (r'^sharing/', include('sharing.urls')),
    (r'^services/', include('services.urls')),
    )
