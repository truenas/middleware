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

from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.views import JsonResp
from freenasUI.tasks import models


def home(request):

    view = appPool.hook_app_index('tasks', request)
    view = filter(None, view)
    if view:
        return view[0]

    tabs = appPool.hook_app_tabs('tasks', request)
    return render(request, 'tasks/index.html', {
        'focused_tab': request.GET.get('tab', 'tasks.CronJob'),
        'hook_tabs': tabs,
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
