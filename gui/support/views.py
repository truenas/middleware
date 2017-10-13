# Copyright 2013 iXsystems, Inc.
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
from collections import OrderedDict
import json
import logging
import os
import requests

from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from wsgiref.util import FileWrapper

from freenasUI.common.system import get_sw_name
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client, ClientException
from freenasUI.middleware.notifier import notifier
from freenasUI.support import forms, utils

log = logging.getLogger("support.views")
TICKET_PROGRESS = '/tmp/.ticketprogress'


def index(request):
    sw_name = get_sw_name().lower()

    license, reason = utils.get_license()
    allow_update = True
    if hasattr(notifier, 'failover_status'):
        status = notifier().failover_status()
        if status not in ('MASTER', 'SINGLE'):
            allow_update = False

    context = {
        'sw_name': sw_name,
        'license': license,
        'fc_enabled': utils.fc_enabled(),
        'allow_update': allow_update,
    }
    for c in appPool.hook_view_context('support.index', request):
        context.update(c)

    return render(request, 'support/home.html', context)


def license_update(request):

    license, reason = utils.get_license()
    if request.method == 'POST':
        form = forms.LicenseUpdateForm(request.POST)
        if form.is_valid():
            with open(utils.LICENSE_FILE, 'wb+') as f:
                f.write(form.cleaned_data.get('license').encode('ascii'))
            events = []
            try:
                _n = notifier()
                if not _n.is_freenas():
                    with client as c:
                        _n.sync_file_send(c, utils.LICENSE_FILE)
                form.done(request, events)
            except Exception as e:
                log.debug("Failed to sync license file: %s", e, exc_info=True)
            return JsonResp(
                request,
                events=events,
                message=_('License updated.')
            )
        else:
            return JsonResp(request, form=form)
    else:
        _n = notifier()
        try:
            if not _n.is_freenas() and _n.failover_licensed():
                with client as c:
                    c.call('failover.call_remote', 'core.ping')
        except ClientException:
            return render(request, 'failover/failover_down.html')
        form = forms.LicenseUpdateForm()

    eula = None
    if not notifier().is_freenas():
        if os.path.exists('/usr/local/share/truenas/eula'):
            with open('/usr/local/share/truenas/eula', 'r', encoding='utf8') as f:
                eula = f.read()

    return render(request, 'support/license_update.html', {
        'eula': eula,
        'form': form,
        'license': license,
    })


def license_status(request):

    sw_name = get_sw_name().lower()
    license, reason = utils.get_license()
    if (
        license is None and sw_name != 'freenas'
    ) or (
        license is not None and license.expired
    ):
        return HttpResponse('PROMPT')

    return HttpResponse('OK')


@require_POST
def ticket(request):

    debug = True if request.POST.get('debug') == 'on' else False

    data = {
        'title': request.POST.get('subject'),
        'body': request.POST.get('desc'),
        'category': request.POST.get('category'),
        'attach_debug': debug,
    }

    if get_sw_name().lower() == 'freenas':
        data.update({
            'username': request.POST.get('username'),
            'password': request.POST.get('password'),
            'type': request.POST.get('type', '').upper(),
        })
    else:
        data.update({
            'phone': request.POST.get('phone'),
            'name': request.POST.get('name'),
            'email': request.POST.get('email'),
            'criticality': request.POST.get('criticality'),
            'environment': request.POST.get('environment'),
        })

    error = False
    files = request.FILES.getlist('attachment')
    token = None
    with client as c:
        try:
            rv = c.call('support.new_ticket', data, job=True)
            data = {'error': False, 'message': rv['url']}
            if files:
                token = c.call('auth.generate_token')
        except ClientException as e:
            data = {'error': True, 'message': e.error}

    if not error:
        for f in files:
            requests.post(
                f'http://127.0.0.1:6000/_upload/?auth_token={token}',
                files={
                    'file': ('file', f.file),
                    'data': ('data', json.dumps({
                        'method': 'support.attach_ticket',
                        'params': [{
                            'ticket': rv['ticket'],
                            'filename': f.name,
                            'username': request.POST.get('username'),
                            'password': request.POST.get('password'),
                        }],
                    }).encode()),
                },
            )

    data = '<html><body><textarea>{}</textarea></boby></html>'.format(
        json.dumps(data),
    )
    return HttpResponse(data)


@require_POST
def ticket_categories(request):
    with client as c:
        try:
            msg = c.call('support.fetch_categories', request.POST.get('user'), request.POST.get('password'))
            success = True
        except ClientException as e:
            success = False
            msg = e.error

    data = {
        'error': not success,
    }

    if success:
        data['categories'] = OrderedDict(
            sorted([('------', '')] + list(msg.items()), key=lambda y: y[0].lower())
        )
    else:
        data['message'] = msg

    return HttpResponse(json.dumps(data), content_type='application/json')


def ticket_progress(request):
    try:
        with client as c:
            jobs = c.call('core.get_jobs', [('method', '=', 'support.new_ticket')], {'order_by': ['-id']})
            job = jobs[0]
            assert job['state'] == 'RUNNING'
            data = {
                'percent': job['progress']['percent'],
                'details': job['progress']['description'],
            }
    except Exception:
        data = {'indeterminate': True}
    return HttpResponse(json.dumps(data), content_type='application/json')


def download_guide(request):
    if not notifier().is_freenas():
        pdf_path = '/usr/local/www/data/docs/TrueNAS.pdf'
        with open(pdf_path, 'rb') as f:
            wrapper = FileWrapper(f)
            response = HttpResponse(wrapper, content_type='application/pdf')
            response['Content-Length'] = os.path.getsize(pdf_path)
            response['Content-Disposition'] = 'attachment; filename=TrueNAS_Userguide.pdf'
            return response
