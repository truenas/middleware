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

import json
import logging
import os
import rollbar
import sys

from django.http import HttpResponse, HttpResponseRedirect
from django.views import debug
from django.template import Context, RequestContext
from django.template.loader import get_template, render_to_string

from freenasUI.common.system import get_sw_version
from freenasUI.system.models import Advanced

log = logging.getLogger('freeadmin.views')


class JsonResp(HttpResponse):

    error = False
    type = 'page'
    force_json = False
    message = ''
    events = []
    confirm = None

    def __init__(self, request, *args, **kwargs):

        self.error = kwargs.pop('error', False)
        self.message = kwargs.pop('message', '')
        self.events = kwargs.pop('events', [])
        self.force_json = kwargs.pop('force_json', False)
        self.type = kwargs.pop('type', None)
        self.template = kwargs.pop('template', None)
        self.form = kwargs.pop('form', None)
        self.confirm = kwargs.pop('confirm', None)
        self.formsets = kwargs.pop('formsets', {})
        self.request = request

        if self.form:
            self.type = 'form'
        elif self.message:
            self.type = 'message'
        if not self.type:
            self.type = 'page'
        if self.confirm:
            self.type = 'confirm'

        data = dict()

        if self.type == 'page':
            ctx = RequestContext(request, kwargs.pop('ctx', {}))
            content = render_to_string(self.template, ctx)
            kwargs['content'] = content
            return super(JsonResp, self).__init__(*args, **kwargs)
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

            for name, fsinfo in self.formsets.items():
                fs = fsinfo['instance']
                fserrors = fs.non_form_errors()
                if fserrors:
                    error = True
                    errors["%s-__all__" % name] = [unicode(e) for e in fserrors]

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
        elif self.type == 'confirm':
            data.update({
                'confirm': self.confirm,
                'error': self.error,
                'type': 'confirm',
            })
        else:
            raise NotImplementedError

        data.update({
            'events': self.events,
        })

        if request.is_ajax() or self.force_json:
            kwargs['content'] = json.dumps(data)
            kwargs['content_type'] = 'application/json'
        else:
            kwargs['content'] = (
                "<html><body><textarea>"
                + json.dumps(data) +
                "</textarea></boby></html>"
            )
        super(JsonResp, self).__init__(*args, **kwargs)

    @staticmethod
    def form_field_all(form):
        if form.prefix:
            field = form.prefix + "-__all__"
        else:
            field = "__all__"
        return field


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
        data = self.get_traceback_data()
        data.update({
            'sw_version': get_sw_version(),
        })
        c = Context(data)
        return t.render(c)


def server_error(request, *args, **kwargs):
    # Save exc info before next exception occurs
    exc_info = sys.exc_info()
    try:
        tb = Advanced.objects.all().latest('id').adv_traceback
    except:
        tb = True

    try:
        extra_data = {
            'sw_version': get_sw_version(),
        }
        for path, name in (
            ('/data/update.failed', 'update_failed'),
            ('/var/log/debug.log', 'debug_log'),
        ):
            if os.path.exists(path):
                with open(path, 'r') as f:
                    extra_data[name] = f.read()[-10240:]
        rollbar.report_exc_info(exc_info, request, extra_data=extra_data)
    except:
        log.warn('Failed to report error', exc_info=True)
    try:
        if tb:
            reporter = ExceptionReporter(request, *exc_info)
            html = reporter.get_traceback_html()
            return HttpResponse(html, content_type='text/html')
        else:
            raise
    except Exception:
        return debug.technical_500_response(request, *exc_info)


def page_not_found(request, *args, **kwargs):
    if request.path.startswith('/api/'):
        return HttpResponse('Endpoint not found', status=404)
    return HttpResponseRedirect('/')
