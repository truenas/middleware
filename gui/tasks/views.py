# +
# Copyright 2014 iXsystems, Inc.
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
from django.utils.translation import ugettext as _
from django.http import HttpResponse

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.tasks import models
from freenasUI.account.models import bsdUsers
import subprocess
import json


def home(request):

    view = appPool.hook_app_index('tasks', request)
    view = filter(None, view)
    if view:
        return view[0]

    return render(request, 'tasks/index.html', {
        'tab': request.GET.get('tab', 'tasks.CronJob'),
    })


def cron_run(request, oid):
    cron = models.CronJob.objects.get(pk=oid)
    if request.method == "POST":
        cron.run()
        return JsonResp(request, message=_("The cron process has started"))

    return render(request, 'tasks/cron_run.html', {
        'cron': cron,
    })


def rsync_run(request, oid):
    rsync = models.Rsync.objects.get(pk=oid)
    if request.method == "POST":
        rsync.run()
        return JsonResp(request, message=_("The rsync process has started"))

    return render(request, 'tasks/rsync_run.html', {
        'rsync': rsync,
    })


def rsync_keyscan(request):
    ruser = request.POST.get("user")
    rhost = request.POST.get("host")
    rport = request.POST.get("port")
    if not ruser:
        data = {'error': True, 'errmsg': _('Please enter a username')}
        return HttpResponse(json.dumps(data))
    else:
        user = bsdUsers.objects.get(bsdusr_username=ruser)
        ruser_path = user.bsdusr_home

    if not rhost:
        data = {'error': True, 'errmsg': _('Please enter a hostname')}
    else:
        if '@' in rhost:
            remote = rhost.split("@")
            remote_host = remote[1]
        else:
            remote_host = rhost

        proc = subprocess.Popen([
            "/usr/bin/ssh-keyscan",
            "-p", str(rport),
            "-T", "2",
            str(remote_host),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        host_key, errmsg = proc.communicate()
        if proc.returncode == 0 and host_key:
            with open(ruser_path + "/.ssh/known_hosts", "a") as myfile:
                myfile.write(host_key)
            data = {'error': False}
        elif not errmsg:
            errmsg = _("Key could not be retrieved for unknown reason")
            data = {'error': True, 'errmsg': errmsg}
        else:
            data = {'error': True, 'errmsg': errmsg}

    return HttpResponse(json.dumps(data))
