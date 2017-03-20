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

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client
from freenasUI.vm import models, utils


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
