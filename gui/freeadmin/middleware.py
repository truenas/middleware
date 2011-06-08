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
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.cache import patch_vary_headers
from django.utils import translation

from system.models import Settings

def public(f):
    f.__is_public = True
    return f

class RequireLoginMiddleware(object):
    """
    Middleware component that makes every view be login_required
    unless its decorated with @public
    """
    def process_view(self,request,view_func,view_args,view_kwargs):
        if request.path == settings.LOGIN_URL:
            return None
        if hasattr(view_func, '__is_public'):
            return None
        return login_required(view_func)(request,*view_args,**view_kwargs)

class LocaleMiddleware(object):

    def process_request(self, request):
        if request.method == 'GET' and 'lang' in request.GET:
                language = request.GET['lang']
        else:
            #FIXME we could avoid this db hit using a cache, 
            # invalidated when settings are edited
            language = Settings.objects.order_by('-id')[0].stg_language

        for lang in settings.LANGUAGES:
            if lang[0] == language:
                translation.activate(language)

    def process_response(self, request, response):
        patch_vary_headers(response, ('Accept-Language',))
        if 'Content-Language' not in response:
            response['Content-Language'] = translation.get_language()
        translation.deactivate()
        return response
