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

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client
from freenasUI.vm import models, utils

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


def start(request, id):
    vm = models.VM.objects.get(id=id)
    raw_file_cnt = None
    raw_file_resize = 0
    if request.method == 'POST':
        if vm.vm_type == 'Container Provider':
            devices = models.Device.objects.filter(vm__id=vm.id)
            for device in devices:
                if device.dtype == 'RAW' and device.attributes.get('boot'):
                    raw_file_cnt = device.attributes.get('path')
                    raw_file_resize = device.attributes.get('size')

            with client as c:
                job_id = c.call('vm.fetch_image', 'RancherOS')
                status = None
                while status != 'SUCCESS':
                    __call = c.call('vm.get_download_status', job_id)
                    status = __call.get('state')
                    utils.dump_download_progress(__call)
                    if status == 'FAILED':
                        return HttpResponse('Error: Image download failed!')
                    elif status == 'ABORTED':
                        return HttpResponse('Error: Download aborted!')
                if status == 'SUCCESS':
                    prebuilt_image = c.call('vm.image_path', 'RancherOS')
                    if prebuilt_image and raw_file_cnt:
                        c.call('vm.decompress_gzip', prebuilt_image, raw_file_cnt)
                        c.call('vm.raw_resize', raw_file_cnt, raw_file_resize)
                    elif prebuilt_image is False:
                        return HttpResponse('Error: Checksum error in downloaded image. Image removed. Please retry.')
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
        url_vnc = c.call('vm.get_vnc_web', id)
    return render(request, "vm/vncweb.html", {
        'name': vm.name,
        'url_vnc': url_vnc[0] if url_vnc else url_vnc,
    })


def download_progress(request):
    return HttpResponse(
        json.dumps(utils.load_progress()), content_type='application/json',
    )
