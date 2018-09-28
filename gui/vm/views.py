# +
# Copyright 2016 ZFStor
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
from django.shortcuts import render
from django.http import HttpResponse
from django.utils.translation import ugettext as _

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client, ValidationErrors
from freenasUI.middleware.form import handle_middleware_validation
from freenasUI.vm import forms, models, utils

import json


def home(request):

    if not utils.vm_enabled():
        return render(request, 'vm/disabled.html')

    view = appPool.hook_app_index('vm', request)
    view = list(filter(None, view))
    if view:
        return view[0]

    tabs = appPool.hook_app_tabs('vm', request)
    return render(request, 'vm/index.html', {
        'focused_tab': request.GET.get('tab', 'vm.VM'),
        'hook_tabs': tabs,
    })


def add(request):

    if request.method == 'POST':
        uuid = request.GET.get('uuid')
        if uuid:
            with client as c:
                jobs = c.call('core.get_jobs', [('id', '=', int(uuid))])
                if jobs:
                    job = jobs[0]
                    if job['state'] in ('FAILED', 'ABORTED'):
                        initial = request.session.get('vm_add') or {}
                        form = forms.VMForm(initial)
                        form.is_valid()
                        form._errors['__all__'] = form.error_class([f'Error creating VM: {job.get("error")}'])
                        return render(request, 'vm/vm_add.html', {
                            'form': form,
                        })
                    elif job['state'] == 'SUCCESS':
                        return JsonResp(
                            request,
                            message=_('VM has been successfully created.'),
                        )
                return HttpResponse(uuid, status=202)
        form = forms.VMForm(request.POST)
        if form.is_valid():
            try:
                obj = form.save()
            except ValidationErrors as e:
                handle_middleware_validation(form, e)
            else:
                if isinstance(obj, int):
                    request.session['vm_add'] = request.POST.copy()
                    request.session['vm_add_job'] = obj
                    return HttpResponse(obj, status=202)
                return JsonResp(request, message=_('VM has been successfully created.'))
        return JsonResp(request, form=form)
    else:
        request.session['vm_add_job'] = None
        form = forms.VMForm()

    return render(request, 'vm/vm_add.html', {
        'form': form,
    })


def add_progress(request):
    jobid = request.session.get('vm_add_job')
    data = {'indeterminate': True}
    if jobid:
        try:
            with client as c:
                jobs = c.call('core.get_jobs', [('id', '=', int(jobid))])
                if jobs:
                    job = jobs[0]
                    data.update({
                        'finished': job['state'] in ('SUCCESS', 'FAILED', 'ABORTED'),
                        'error': job['error'],
                        'percent': job['progress'].get('percent'),
                        'indeterminate': True if job['progress']['percent'] is None else False,
                        'details': job['progress'].get('description'),
                        'step': 1,
                    })
        except Exception:
            pass
    return HttpResponse(json.dumps(data), content_type='application/json')


def start(request, id):
    vm = models.VM.objects.get(id=id)
    if request.method == 'POST':
        with client as c:
            c.call('vm.start', id)
        return JsonResp(request, message='VM Started')
    return render(request, "vm/start.html", {
        'name': vm.name,
    })


def stop(request, id):
    vm = models.VM.objects.get(id=id)
    if request.method == 'POST':
        with client as c:
            c.call('vm.stop', id)
        return JsonResp(request, message='VM Stopped')
    return render(request, "vm/stop.html", {
        'name': vm.name,
    })


def power_off(request, id):
    vm = models.VM.objects.get(id=id)
    if request.method == 'POST':
        with client as c:
            c.call('vm.stop', id, True)
        return JsonResp(request, message='VM Powered off')
    return render(request, "vm/poweroff.html", {
        'name': vm.name,
    })


def restart(request, id):
    vm = models.VM.objects.get(id=id)
    if request.method == 'POST':
        with client as c:
            c.call('vm.restart', id)
        return JsonResp(request, message='VM Restarted')
    return render(request, "vm/restart.html", {
        'name': vm.name,
    })


def clone(request, id):
    vm = models.VM.objects.get(id=id)
    if request.method == 'POST':
        with client as c:
            c.call('vm.clone', id)
        return JsonResp(request, message='VM Cloned')
    return render(request, "vm/clone.html", {
        'name': vm.name,
    })


def vnc_web(request, id):
    vm = models.VM.objects.get(id=id)
    url_vnc = None
    with client as c:
        url_vnc = c.call('vm.get_vnc_web', id, request.META['HTTP_HOST'].split(':')[0])
    return render(request, "vm/vncweb.html", {
        'name': vm.name,
        'url_vnc': url_vnc[0] if url_vnc else url_vnc,
    })


def download_progress(request):
    return HttpResponse(
        json.dumps(utils.load_progress()), content_type='application/json',
    )
