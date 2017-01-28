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
import socket
import subprocess
import time

from django.core.files.base import File
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST
from wsgiref.util import FileWrapper

from freenasUI.common.system import get_sw_name, get_sw_version
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import GlobalConfiguration
from freenasUI.support import forms, utils
from freenasUI.system.utils import debug_get_settings, debug_generate

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
        _n = notifier()
        try:
            if not _n.is_freenas() and _n.failover_licensed():
                s = _n.failover_rpc()
                s.ping()
        except socket.error:
            return render(request, 'failover/failover_down.html')
        form = forms.LicenseUpdateForm()

    eula = None
    if not notifier().is_freenas():
        if os.path.exists('/usr/local/share/truenas/eula'):
            with open('/usr/local/share/truenas/eula', 'r') as f:
                eula = f.read().decode('utf8')

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

    step = 2 if request.FILES.getlist('attachment') else 1

    files = []
    if request.POST.get('debug') == 'on':
        debug = True
        with open(TICKET_PROGRESS, 'w') as f:
            f.write(json.dumps({'indeterminate': True, 'step': step}))
        step += 1

        mntpt, direc, dump = debug_get_settings()
        debug_generate()

        _n = notifier()
        if not _n.is_freenas() and _n.failover_licensed():
            debug_file = '%s/debug.tar' % direc
            debug_name = 'debug-%s.tar' % time.strftime('%Y%m%d%H%M%S')
        else:
            gc = GlobalConfiguration.objects.all().order_by('-id')[0]
            debug_file = dump
            debug_name = 'debug-%s-%s.txz' % (
                gc.gc_hostname.encode('utf-8'),
                time.strftime('%Y%m%d%H%M%S'),
            )

        files.append(File(open(debug_file, 'rb'), name=debug_name))
    else:
        debug = False

    with open(TICKET_PROGRESS, 'w') as f:
        f.write(json.dumps({'indeterminate': True, 'step': step}))
    step += 1

    data = {
        'title': request.POST.get('subject'),
        'body': request.POST.get('desc'),
        'version': get_sw_version().split('-', 1)[-1],
        'category': request.POST.get('category'),
        'debug': debug,
    }

    if get_sw_name().lower() == 'freenas':
        data.update({
            'user': request.POST.get('username'),
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

    success, msg, tid = utils.new_ticket(data)

    with open(TICKET_PROGRESS, 'w') as f:
        f.write(json.dumps({'indeterminate': True, 'step': step}))
    step += 1

    data = {'message': msg, 'error': not success}

    if not success:
        pass
    else:

        files.extend(request.FILES.getlist('attachment'))
        for f in files:
            success, attachmsg = utils.ticket_attach({
                'user': request.POST.get('username'),
                'password': request.POST.get('password'),
                'ticketnum': tid,
            }, f)

    data = (
        '<html><body><textarea>%s</textarea></boby></html>' % (
            json.dumps(data),
        )
    )
    return HttpResponse(data)


@require_POST
def ticket_categories(request):
    success, msg = utils.fetch_categories({
        'user': request.POST.get('user'),
        'password': request.POST.get('password'),
    })
    data = {
        'error': not success,
    }

    if success:
        data['categories'] = OrderedDict(
            sorted([('------', '')] + msg.items(), key=lambda y: y[0].lower())
        )
    else:
        data['message'] = msg

    return HttpResponse(json.dumps(data), content_type='application/json')


def ticket_progress(request):
    with open(TICKET_PROGRESS, 'r') as f:
        try:
            data = json.loads(f.read())
        except:
            data = {'indeterminate': True}
    return HttpResponse(json.dumps(data), content_type='application/json')


def donwload_guide(request):
    if not notifier().is_freenas():
        pdf_path = '/usr/local/www/data/docs/TrueNAS.pdf'
        with open(pdf_path, 'rb') as f:
            wrapper = FileWrapper(f)
            response = HttpResponse(wrapper, content_type='application/pdf')
            response['Content-Length'] = os.path.getsize(pdf_path)
            response['Content-Disposition'] = 'attachment; filename=TrueNAS_Userguide.pdf'
            return response
