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
from cStringIO import StringIO

import json
import logging
import re
import sys
import cProfile

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.utils import OperationalError
from django.http import HttpResponse
from django.utils import translation
from django.utils.cache import patch_vary_headers
from django.utils.translation import ugettext as _
import oauth2 as oauth

from freenasUI import settings as mysettings
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.services.models import RPCToken
from freenasUI.system.models import Settings

log = logging.getLogger('freeadmin.middleware')

COMMENT_SYNTAX = (
    (re.compile(r'^application/(.*\+)?xml|text/html$', re.I), '<!--', '-->'),
    (re.compile(r'^application/j(avascript|son)$', re.I), '/*', '*/'),
)


def public(f):
    f.__is_public = True
    return f


def http_oauth(func):

    def view(request, *args, **kwargs):
        authorized = False
        json_params = {}
        oauth_params = {}

        try:
            for key in request.GET:
                if key.startswith("oauth"):
                    oauth_params[key] = request.GET.get(key)
                else:
                    json_params = json.loads(key)

            for key in request.POST:
                if key.startswith("oauth"):
                    oauth_params[key] = request.POST.get(key)

            key = oauth_params.get("oauth_consumer_key", None)
            host = "%s://%s" % (
                'https' if request.is_secure() else 'http',
                request.get_host(),
            )
            uurl = host + request.path

            oreq = oauth.Request(request.method, uurl, oauth_params, '', False)
            server = oauth.Server()

            secret = None
            rpctoken = RPCToken.objects.get(key=key)
            if rpctoken:
                secret = rpctoken.secret

            if not key or not secret:
                raise Exception

            try:
                cons = oauth.Consumer(key, secret)
                server.add_signature_method(oauth.SignatureMethod_HMAC_SHA1())
                server.verify_request(oreq, cons, None)
                authorized = True

            except Exception, e:
                log.debug("auth error = %s" % e)
                authorized = False

            if request.method == "POST":
                method = json_params.get("method")

                if method in (
                    'plugins.is_authenticated',
                ):
                    authorized = True

            if authorized:
                return func(request, *args, **kwargs)

        except Exception, e:
            log.debug('OAuth authentication failed', exc_info=True)

        return HttpResponse(json.dumps({
            'jsonrpc': json_params.get("jsonrpc", "2.0"),
            'error': {
                'code': '500',
                'message': 'Not authenticated',
            },
            'id': json_params.get("id", "1"),
        }))

    return view


class RequireLoginMiddleware(object):
    """
    Middleware component that makes every view be login_required
    unless its decorated with @public
    """
    def process_view(self, request, view_func, view_args, view_kwargs):

        # Bypass this middleware in case URLCONF is different
        # This is required so django tests can run
        if settings.ROOT_URLCONF != mysettings.ROOT_URLCONF:
            return None
        # Login url is cleared
        if request.path == settings.LOGIN_URL:
            return None
        # API use its own authentication method
        if request.path.startswith('/api/'):
            return None
        if hasattr(view_func, '__is_public'):
            return None

        # JSON-RPC calls are authenticated through HTTP Basic
        if request.path.startswith('/plugins/json-rpc/'):
            return http_oauth(view_func)(request, *view_args, **view_kwargs)

        return login_required(view_func)(request, *view_args, **view_kwargs)


class LocaleMiddleware(object):

    def process_request(self, request):

        # Limit language select in the wizard to the wizard
        if (
            'wizard_lang' in request.session and
            request.path == '/system/wizard/'
        ):
            translation.activate(request.session['wizard_lang'])
            return None

        language = None
        if request.method == 'GET' and 'lang' in request.GET:
            for lang in settings.LANGUAGES:
                if lang[0] == request.GET['lang']:
                    language = lang[0]
                    break

        if not language:
            # FIXME: we could avoid this db hit using a cache,
            # invalidated when settings are edited
            language = Settings.objects.order_by('-id')[0].stg_language

        translation.activate(language)

    def process_response(self, request, response):
        patch_vary_headers(response, ('Accept-Language',))
        if 'Content-Language' not in response:
            response['Content-Language'] = translation.get_language()
        translation.deactivate()
        return response


class CatchError(object):

    def process_response(self, request, response):
        exc_info = sys.exc_info()
        if exc_info[0] and exc_info[0] in (
            MiddlewareError, ServiceFailed, OperationalError
        ):
            excp = exc_info[1]
            kwargs = {
                'error': True,
                'message': _("Error: %s") % (
                    unicode(excp.value)
                    if exc_info[0] is not OperationalError
                    else unicode(excp.message)
                ),
            }
            return JsonResp(request, **kwargs)
        return response


class ProfileMiddleware(object):
    """
    Based on
    http://www.no-ack.org/2010/12/yet-another-profiling-middleware-for.html

    Changed to cProfile, instead of hotshot
    """
    def process_view(self, request, callback, args, kwargs):
        self.profiler = cProfile.Profile()
        return self.profiler.runcall(callback, request, *args, **kwargs)

    def process_response(self, request, response):

        if not hasattr(self, "profiler"):
            return response
        self.profiler.create_stats()
        out = StringIO()
        old_stdout, sys.stdout = sys.stdout, out
        self.profiler.print_stats(1)
        sys.stdout = old_stdout

        # If we have got a 3xx status code, further
        # action needs to be taken by the user agent
        # in order to fulfill the request. So don't
        # attach any stats to the content, because of
        # the content is supposed to be empty and is
        # ignored by the user agent.
        if response.status_code // 100 == 3:
            return response

        # Detect the appropriate syntax based on the
        # Content-Type header.
        for regex, begin_comment, end_comment in COMMENT_SYNTAX:
            if regex.match(response['Content-Type'].split(';')[0].strip()):
                break
        else:
            # If the given Content-Type is not
            # supported, don't attach any stats to
            # the content and return the unchanged
            # response.
            return response

        # The response can hold an iterator, that
        # is executed when the content property
        # is accessed. So we also have to profile
        # the call of the content property.
        content = out.getvalue()

        # Construct an HTML/XML or Javascript comment, with
        # the formatted stats, written to the StringIO object
        # and attach it to the content of the response.
        comment = '\n%s\n\n%s\n\n%s\n' % (
            begin_comment, content, end_comment,
        )
        response.content += comment

        # If the Content-Length header is given, add the
        # number of bytes we have added to it. If the
        # Content-Length header is ommited or incorrect,
        # it remains so in order to don't change the
        # behaviour of the web server or user agent.
        if response.has_header('Content-Length'):
            response['Content-Length'] = int(response['Content-Length']) + \
                len(comment)

        return response
