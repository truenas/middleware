#+
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
import subprocess

from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from django.core.files.uploadedfile import TemporaryUploadedFile

from dispatcher.rpc import RpcException
from freenasUI.common.system import get_sw_name
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.connector import connection as dispatcher
from freenasUI.middleware.notifier import notifier
from freenasUI.support import forms, utils
from freenasUI.system.utils import debug_get_settings, debug_run

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
                    s = _n.failover_rpc()
                    if s is not None:
                        _n.sync_file_send(s, utils.LICENSE_FILE)
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
        form = forms.LicenseUpdateForm()
    return render(request, 'support/license_update.html', {
        'form': form,
        'license': license,
    })


def license_status(request):

    sw_name = get_sw_name().lower()
    license, reason = utils.get_license()
    if (license is None and sw_name != 'freenas') or license.expired:
        return HttpResponse('PROMPT')

    return HttpResponse('OK')


@require_POST
def ticket(request):

    step = 2 if request.FILES.getlist('attachment') else 1

    files = []
    if request.POST.get('debug') == 'on':
        debug = True
        with open(TICKET_PROGRESS, 'w') as f:
            f.write(json.dumps({'indeterminate': True, 'step': step}))
        step += 1

        mntpt, direc, dump = debug_get_settings()
        debug_run(direc)
        files.append(dump)
    else:
        debug = False

    with open(TICKET_PROGRESS, 'w') as f:
        f.write(json.dumps({'indeterminate': True, 'step': step}))
    step += 1

    data = {
        'subject': request.POST.get('subject'),
        'description': request.POST.get('desc'),
        'category': request.POST.get('category'),
        'debug': debug,
    }

    if get_sw_name().lower() == 'freenas':
        data.update({
            'username': request.POST.get('username'),
            'password': request.POST.get('password'),
            'type': request.POST.get('type'),
        })
    else:

        serial = subprocess.Popen(
            ['/usr/local/sbin/dmidecode', '-s', 'system-serial-number'],
            stdout=subprocess.PIPE
        ).communicate()[0].split('\n')[0].upper()

        license, reason = utils.get_license()
        if license:
            company = license.customer_name
        else:
            company = 'Unknown'

        data.update({
            'phone': request.POST.get('phone'),
            'name': request.POST.get('name'),
            'company': company,
            'email': request.POST.get('email'),
            'criticality': request.POST.get('criticality'),
            'environment': request.POST.get('environment'),
            'serial': serial,
        })

    for f in request.FILES.getlist('attachment'):
        if not isinstance(f, TemporaryUploadedFile):
            tmpfile = '/tmp/%s' % f.name
            with open(tmpfile, 'wb') as fh:
                for chunk in f.chunks():
                    fh.write(chunk)
            files.append(tmpfile)
        else:
            files.append(f.temporary_file_path())

    if files:
        data['attachments'] = files

    task = dispatcher.call_task_sync('support.submit', data)
    if task['state'] != 'FINISHED':
        data = {
            'error': True,
            'message': task['error']['message'],
        }
    else:
        data = {
            'error': False,
            'message': task['result'][1],
        }

    for f in files:
        try:
            os.unlink(f)
        except:
            pass

    data = (
        '<html><body><textarea>%s</textarea></boby></html>' % (
            json.dumps(data),
        )
    )
    return HttpResponse(data)


@require_POST
def ticket_categories(request):
    data = {}
    try:
        categories = dispatcher.call_sync(
            'support.categories', request.POST.get('user'), request.POST.get('password')
        )
        data['categories'] = OrderedDict(
            sorted([('------', '')] + categories.items(), key=lambda y: y[0].lower())
        )
    except RpcException, e:
        data['error'] = True
        data['message'] = str(e)
    else:
        data['error'] = False

    return HttpResponse(json.dumps(data), content_type='application/json')


def ticket_progress(request):
    with open(TICKET_PROGRESS, 'r') as f:
        try:
            data = json.loads(f.read())
        except:
            data = {'indeterminate': True}
    return HttpResponse(json.dumps(data), content_type='application/json')
