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
from collections import namedtuple
import logging

import eventlet

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.middleware.notifier import notifier
from freenasUI.plugins.models import Plugins
from freenasUI.plugins.utils import get_base_url, get_plugin_status
from freenasUI.services import models
from freenasUI.services.directoryservice import DirectoryService

log = logging.getLogger("services.views")


def index(request):
    return render(request, 'services/index.html', {
        'toggleCore': request.GET.get('toggleCore'),
    })


def plugins(request):

    Service = namedtuple('Service', [
        'name',
        'status',
        'pid',
        'start_url',
        'stop_url',
        'status_url',
        ])

    host = get_base_url(request)
    plugins = Plugins.objects.filter(plugin_enabled=True)
    args = map(lambda y: (y, host, request), plugins)

    pool = eventlet.GreenPool(20)
    for plugin, json in pool.imap(get_plugin_status, args):

        if not json:
            continue

        plugin.service = Service(
            name=plugin.plugin_name,
            status=json['status'],
            pid=json.get("pid", None),
            start_url="/plugins/%s/_s/start" % (plugin.plugin_name, ),
            stop_url="/plugins/%s/_s/stop" % (plugin.plugin_name, ),
            status_url="/plugins/%s/_s/status" % (plugin.plugin_name, ),
            )

    srv_enable = False
    s = models.services.objects.filter(srv_service='plugins')
    if s:
        s = s[0]
        srv_enable = s.srv_enable

    jail_configured = notifier().plugins_jail_configured() and \
        notifier()._started_plugins_jail() and srv_enable

    return render(request, "services/plugins.html", {
        'plugins': plugins,
        'jail_configured': jail_configured,
    })


def core(request):

    try:
        directoryservice = DirectoryService.objects.order_by("-id")[0]
    except IndexError:
        try:
            directoryservice = DirectoryService.objects.create()
        except:
            directoryservice = None

    try:
        afp = models.AFP.objects.order_by("-id")[0]
    except IndexError:
        afp = models.AFP.objects.create()

    try:
        cifs = models.CIFS.objects.order_by("-id")[0]
    except IndexError:
        cifs = models.CIFS.objects.create()

    try:
        dynamicdns = models.DynamicDNS.objects.order_by("-id")[0]
    except IndexError:
        dynamicdns = models.DynamicDNS.objects.create()

    try:
        nfs = models.NFS.objects.order_by("-id")[0]
    except IndexError:
        nfs = models.NFS.objects.create()

    try:
        ftp = models.FTP.objects.order_by("-id")[0]
    except IndexError:
        ftp = models.FTP.objects.create()

    try:
        tftp = models.TFTP.objects.order_by("-id")[0]
    except IndexError:
        tftp = models.TFTP.objects.create()

    try:
        rsyncd = models.Rsyncd.objects.order_by("-id")[0]
    except IndexError:
        rsyncd = models.Rsyncd.objects.create()

    try:
        smart = models.SMART.objects.order_by("-id")[0]
    except IndexError:
        smart = models.SMART.objects.create()

    try:
        snmp = models.SNMP.objects.order_by("-id")[0]
    except IndexError:
        snmp = models.SNMP.objects.create()

    try:
        ssh = models.SSH.objects.order_by("-id")[0]
    except IndexError:
        ssh = models.SSH.objects.create()

    try:
        ups = models.UPS.objects.order_by("-id")[0]
    except IndexError:
        ups = models.UPS.objects.create()

    plugins = None
    try:
        if notifier().plugins_jail_configured():
            plugins = models.PluginsJail.objects.order_by("-id")[0]
    except IndexError:
        plugins = None

    srv = models.services.objects.all()
    return render(request, 'services/core.html', {
        'srv': srv,
        'cifs': cifs,
        'afp': afp,
        'nfs': nfs,
        'rsyncd': rsyncd,
        'dynamicdns': dynamicdns,
        'snmp': snmp,
        'ups': ups,
        'ftp': ftp,
        'tftp': tftp,
        'smart': smart,
        'ssh': ssh,
        'plugins': plugins,
        'directoryservice': directoryservice,
        })


def iscsi(request):
    gconfid = models.iSCSITargetGlobalConfiguration.objects.all().order_by(
        "-id")[0].id
    return render(request, 'services/iscsi.html', {
        'focus_tab': request.GET.get('tab', ''),
        'gconfid': gconfid,
        })


def servicesToggleView(request, formname):
    form2namemap = {
        'cifs_toggle': 'cifs',
        'afp_toggle': 'afp',
        'nfs_toggle': 'nfs',
        'iscsitarget_toggle': 'iscsitarget',
        'dynamicdns_toggle': 'dynamicdns',
        'snmp_toggle': 'snmp',
        'httpd_toggle': 'httpd',
        'ftp_toggle': 'ftp',
        'tftp_toggle': 'tftp',
        'ssh_toggle': 'ssh',
        'ldap_toggle': 'ldap',
        'rsync_toggle': 'rsync',
        'smartd_toggle': 'smartd',
        'ups_toggle': 'ups',
        'plugins_toggle': 'plugins',
        'directoryservice_toggle': 'directoryservice',
    }
    changing_service = form2namemap[formname]
    if changing_service == "":
        raise "Unknown service - Invalid request?"

    enabled_svcs = []
    disabled_svcs = []
    directory_services = ['activedirectory', 'ldap', 'nt4', 'nis']

    svc_entry = models.services.objects.get(srv_service=changing_service)
    if changing_service == "directoryservice": 
        directoryservice = DirectoryService.objects.order_by("-id")[0]
       
        for svc in directory_services:
            if svc != directoryservice.svc:
                notifier().stop(svc)

        if svc_entry.srv_enable == 1:
            started = notifier().start(directoryservice.svc)
            if models.services.objects.get(srv_service='cifs').srv_enable:
                enabled_svcs.append('cifs')
        else:
            started = notifier().stop(directoryservice.svc)
            if not models.services.objects.get(srv_service='cifs').srv_enable:
                disabled_svcs.append('cifs')

    if svc_entry.srv_enable:
        svc_entry.srv_enable = 0
    else:
        svc_entry.srv_enable = 1
    svc_entry.save()

    if changing_service != 'directoryservice':
        started = notifier().restart(changing_service)

    error = False
    message = False
    if started is True:
        status = 'on'
        if svc_entry.srv_enable == 0:
            error = True
            message = _("The service could not be stopped.")
            svc_entry.srv_enable = 1
            svc_entry.save()

    elif started is False:
        status = 'off'
        if svc_entry.srv_enable == 1:
            error = True
            message = _("The service could not be started.")
            svc_entry.srv_enable = 0
            svc_entry.save()
            if changing_service in ('ups', 'plugins_jail') or \
                changing_service in directory_services:
                notifier().stop(changing_service)
    else:
        if svc_entry.srv_enable == 1:
            status = 'on'
        else:
            status = 'off'

    data = {
        'service': changing_service,
        'status': status,
        'error': error,
        'message': message,
        'enabled_svcs': enabled_svcs,
        'disabled_svcs': disabled_svcs,
    }

    return HttpResponse(simplejson.dumps(data), mimetype="application/json")


def enable(request, svc):
    return render(request, "services/enable.html", {
        'svc': svc,
    })
