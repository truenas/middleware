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

from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse
from django.utils import simplejson
from django.utils.translation import ugettext as _

from freenasUI.services import models
from freenasUI.middleware.notifier import notifier

def home(request):

    try:
        activedirectory = models.ActiveDirectory.objects.order_by("-id")[0]
    except IndexError:
        activedirectory = models.ActiveDirectory.objects.create()

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

    try:
        ldap = models.LDAP.objects.order_by("-id")[0]
    except IndexError:
        ldap = models.LDAP.objects.create()

    plugins = None
    try:
        if notifier().plugins_jail_configured():
            plugins = models.Plugins.objects.order_by("-id")[0]
    except IndexError:
        plugins = None

    srv = models.services.objects.all()
    return render(request, 'services/index.html', {
        'srv': srv,
        'cifs': cifs,
        'afp': afp,
        'nfs': nfs,
        'rsyncd': rsyncd,
        #'unison': unison,
        'dynamicdns': dynamicdns,
        'snmp': snmp,
        'ups': ups,
        #'webserver': webserver,
        #'bittorrent': bittorrent,
        'ftp': ftp,
        'tftp': tftp,
        'smart': smart,
        'ssh': ssh,
        'activedirectory': activedirectory,
        'ldap': ldap,
        'plugins': plugins,
        })

def iscsi(request):
    gconfid = models.iSCSITargetGlobalConfiguration.objects.all().order_by("-id")[0].id
    return render(request, 'services/iscsi.html', {
        'focus_tab' : request.GET.get('tab',''),
        'gconfid': gconfid,
        })

def iscsi_targets(request):
    target_list = models.iSCSITarget.objects.all()
    return render(request, 'services/iscsi_targets.html', {
        'target_list': target_list,
    })

def iscsi_assoctargets(request, objtype=None):
    asctarget_list = models.iSCSITargetToExtent.objects.all()
    return render(request, 'services/iscsi_assoctargets.html', {
        'asctarget_list': asctarget_list,
    })

def iscsi_extents(request, objtype=None):
    extent_file_list = models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type='File')
    return render(request, 'services/iscsi_extents.html', {
        'extent_file_list': extent_file_list,
    })

def iscsi_dextents(request):
    extent_device_list = models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type__in=['Disk','ZVOL'])
    return render(request, 'services/iscsi_dextents.html', {
        'extent_device_list': extent_device_list,
    })

def iscsi_auth(request):
    target_auth_list = models.iSCSITargetAuthCredential.objects.all()
    return render(request, 'services/iscsi_auth.html', {
        'target_auth_list': target_auth_list,
    })

def iscsi_authini(request):
    auth_initiator_list = models.iSCSITargetAuthorizedInitiator.objects.all()
    return render(request, 'services/iscsi_authini.html', {
        'auth_initiator_list': auth_initiator_list,
    })

def iscsi_portals(request):
    iscsiportal_list = models.iSCSITargetPortal.objects.all()
    return render(request, 'services/iscsi_portals.html', {
        'iscsiportal_list': iscsiportal_list,
    })

def servicesToggleView(request, formname):
    form2namemap = {
        'cifs_toggle' : 'cifs',
        'afp_toggle' : 'afp',
        'nfs_toggle' : 'nfs',
        'iscsitarget_toggle' : 'iscsitarget',
        'dynamicdns_toggle' : 'dynamicdns',
        'snmp_toggle' : 'snmp',
        'httpd_toggle' : 'httpd',
        'ftp_toggle' : 'ftp',
        'tftp_toggle' : 'tftp',
        'ssh_toggle' : 'ssh',
        'activedirectory_toggle' : 'activedirectory',
        'ldap_toggle' : 'ldap',
        'rsync_toggle' : 'rsync',
        'smartd_toggle' : 'smartd',
        'ups_toggle' : 'ups',
        'plugins_toggle' : 'plugins',
    }
    changing_service = form2namemap[formname]
    if changing_service == "":
        raise "Unknown service - Invalid request?"

    # Do not allow LDAP and AD to be enabled simultaniously
    opposing_service = None
    opp_svc_entry = None
    if changing_service == "ldap":
        opposing_service = "activedirectory"
    if changing_service == "activedirectory":
        opposing_service = "ldap"
    svc_entry = models.services.objects.get(srv_service=changing_service)
    if opposing_service:
        opp_svc_entry = models.services.objects.get(srv_service=opposing_service)

    # Turning things off is always ok
    if svc_entry.srv_enable:
        svc_entry.srv_enable = 0
    else:
        if opposing_service and not opp_svc_entry.srv_enable == 1 or not opposing_service:
            svc_entry.srv_enable = 1
    svc_entry.save()

    # forcestop then start to make sure the service is of the same
    # status.
    if changing_service in ("ldap", "activedirectory"):
        if svc_entry.srv_enable == 1:
            started = notifier().start(changing_service)
        else:
            started = notifier().stop(changing_service)
    elif changing_service == 'plugins':
        if svc_entry.srv_enable == 1:
            started = notifier().start('plugins_jail')
        else:
            started = notifier().stop('plugins_jail')
    else:
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
            if changing_service in ('ldap','activedirectory', 'ups'):
                notifier().stop(changing_service)
            elif changing_service == 'plugins':
                notifier().stop('plugins_jail')

    else:
        if svc_entry.srv_enable == 1:
            status ='on'
        else:
            status = 'off'

    data = {
        'service': changing_service,
        'status': status,
        'error': error,
        'message': message,
    }

    return HttpResponse(simplejson.dumps(data), mimetype="application/json")

def rsyncmod(request):
    return render(request, "services/rsyncmod.html", {
        'rsyncmod_list': models.RsyncMod.objects.all(),
        })

def enable(request, svc):
    return render(request, "services/enable.html", {
        'svc': svc,
    })
