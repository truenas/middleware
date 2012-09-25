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

import logging
import hashlib
import sys

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.views import debug
from django.template import Context
from django.template.loader import get_template
from django.utils import simplejson

from freenasUI.common.system import get_sw_name, get_sw_version
from freenasUI.network.models import GlobalConfiguration
from freenasUI.system.models import Advanced

log = logging.getLogger('freeadmin.views')


class JsonResponse(HttpResponse):

    error = False
    enclosed = False
    message = ''
    events = []

    def __init__(self, *args, **kwargs):
        self.error = kwargs.pop('error', False)
        self.message = kwargs.pop('message', '')
        self.events = kwargs.pop('events', [])
        self.enclosed = kwargs.pop('enclosed', False)

        data = {
            'error': self.error,
            'message': self.message,
            'events': self.events,
        }

        if self.enclosed:
            kwargs['content'] = ("<html><body><textarea>"
                + simplejson.dumps(data) +
                "</textarea></boby></html>")
        else:
            kwargs['content'] = simplejson.dumps(data)
            kwargs['content_type'] = 'application/json'
        super(JsonResponse, self).__init__(*args, **kwargs)


class JsonResp(HttpResponse):

    error = False
    type = 'page'
    force_json = False
    message = ''
    events = []

    def __init__(self, request, *args, **kwargs):

        self.error = kwargs.pop('error', False)
        self.message = kwargs.pop('message', '')
        self.events = kwargs.pop('events', [])
        self.force_json = kwargs.pop('force_json', False)
        self.type = kwargs.pop('type', None)
        self.template = kwargs.pop('template', None)
        self.form = kwargs.pop('form', None)
        self.formsets = kwargs.pop('formsets', {})
        self.request = request

        if self.form:
            self.type = 'form'
        elif self.message:
            self.type = 'message'
        if not self.type:
            self.type = 'page'

        data = dict()

        if self.type == 'page':
            pass
            #ctx = RequestContext(request, kwargs.pop('ctx', {}))
            #content = render_to_string(self.template, ctx)
        elif self.type == 'form':
            data.update({
                'type': 'form',
                'formid': request.POST.get("__form_id"),
                })
            error = False
            errors = {}
            if self.form.errors:
                for key, val in self.form.errors.items():
                    if key == '__all__':
                        field = self.__class__.form_field_all(self.form)
                        errors[field] = [unicode(v) for v in val]
                    else:
                        errors[key] = [unicode(v) for v in val]
                error = True

            for name, fs in self.formsets.items():
                for i, form in enumerate(fs.forms):
                    if form.errors:
                        error = True
                        for key, val in form.errors.items():
                            if key == '__all__':
                                field = self.__class__.form_field_all(form)
                                errors[field] = [unicode(v) for v in val]
                            else:
                                errors["%s-%s" % (
                                    form.prefix,
                                    key,
                                    )] = [unicode(v) for v in val]
            data.update({
                'error': error,
                'errors': errors,
                'message': self.message,
            })
        elif self.type == 'message':
            data.update({
                'error': self.error,
                'message': self.message,
            })
        else:
            raise NotImplementedError

        data.update({
            'events': self.events,
        })

        if request.is_ajax() or self.force_json:
            kwargs['content'] = simplejson.dumps(data)
            kwargs['content_type'] = 'application/json'
        else:
            kwargs['content'] = ("<html><body><textarea>"
                + simplejson.dumps(data) +
                "</textarea></boby></html>")
        super(JsonResp, self).__init__(*args, **kwargs)

    @staticmethod
    def form_field_all(form):
        if form.prefix:
            field = form.prefix + "-__all__"
        else:
            field = "__all__"
        return field


def adminInterface(request, objtype=None):

    try:
        console = Advanced.objects.all().order_by('-id')[0].adv_consolemsg
    except:
        console = False
    try:
        hostname = GlobalConfiguration.objects.order_by('-id')[0].gc_hostname
    except:
        hostname = None
    sw_version = get_sw_version()
    return render(request, 'freeadmin/index.html', {
        'consolemsg': console,
        'hostname': hostname,
        'sw_name': get_sw_name(),
        'sw_version': sw_version,
        'cache_hash': hashlib.md5(sw_version).hexdigest(),
    })


class ExceptionReporter(debug.ExceptionReporter):
    """
    We use the django debug 500 classes to show the traceback to the user
    instead of the useless "An error occurred" used by dojo in case of
    HTTP 500 responses.

    As this is not a public API of django we need to duplicate some code
    """

    is_email = False

    def get_traceback_html(self):
        """
        Copied from debug.ExceptionReporter
        The Template was replaced to use 500_freenas.html instead
        of the hard-coded one

        Return HTML code for traceback."
        """

        t = get_template("500_freenas.html")
        #t = Template(TECHNICAL_500_TEMPLATE, name='Technical 500 template')
        data = self.get_traceback_data()
        data.update({
            'sw_version': get_sw_version(),
        })
        c = Context(data)
        return t.render(c)


def server_error(request, *args, **kwargs):
    try:
        adv = Advanced.objects.all().order_by('-id')[0]
        if adv.adv_traceback:
            reporter = ExceptionReporter(request, *sys.exc_info())
            html = reporter.get_traceback_html()
            return HttpResponse(html, mimetype='text/html')
        else:
            raise
    except:
        return debug.technical_500_response(request, *sys.exc_info())


def page_not_found(request, *args, **kwargs):
    return HttpResponseRedirect('/')
