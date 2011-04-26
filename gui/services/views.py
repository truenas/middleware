#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponseRedirect

from freenasUI.services import models
from freenasUI.middleware.notifier import notifier

def home(request):

    try:
        cifs = models.CIFS.objects.order_by("-id")[0]
    except IndexError:
        cifs = None

    try:
        afp = models.AFP.objects.order_by("-id")[0]
    except IndexError:
        afp = None

    try:
        nfs = models.NFS.objects.order_by("-id")[0]
    except IndexError:
        nfs = None

    try:
        dynamicdns = models.DynamicDNS.objects.order_by("-id")[0]
    except IndexError:
        dynamicdns = None

    try:
        snmp = models.SNMP.objects.order_by("-id")[0]
    except IndexError:
        snmp = None

    try:
        ftp = models.FTP.objects.order_by("-id")[0]
    except IndexError:
        ftp = None

    try:
        tftp = models.TFTP.objects.order_by("-id")[0]
    except IndexError:
        tftp = None

    try:
        ssh = models.SSH.objects.order_by("-id")[0]
    except IndexError:
        ssh = None

    try:
        activedirectory = models.ActiveDirectory.objects.order_by("-id")[0]
    except IndexError:
        activedirectory = None

    try:
        ldap = models.LDAP.objects.order_by("-id")[0]
    except IndexError:
        ldap = None

    srv = models.services.objects.all()
    variables = RequestContext(request, {
        'srv': srv,
        'cifs': cifs,
        'afp': afp,
        'nfs': nfs,
        #'rsync': rsync,
        #'unison': unison,
        'dynamicdns': dynamicdns,
        'snmp': snmp,
        #'ups': ups,
        #'webserver': webserver,
        #'bittorrent': bittorrent,
        'ftp': ftp,
        'tftp': tftp,
        'ssh': ssh,
        'activedirectory': activedirectory,
        'ldap': ldap,
        })
    return render_to_response('services/index2.html', variables)

def iscsi(request):
    gconfid = models.iSCSITargetGlobalConfiguration.objects.all().order_by("-id")[0].id
    variables = RequestContext(request, {
        'focus_tab' : request.GET.get('tab',''),
        'gconfid': gconfid,
        })
    return render_to_response('services/iscsi.html', variables)

def iscsi_targets(request):
    target_list = models.iSCSITarget.objects.all()

    variables = RequestContext(request, {
        'target_list': target_list,
    })
    return render_to_response('services/iscsi_targets.html', variables)

def iscsi_assoctargets(request, objtype=None):
    asctarget_list = models.iSCSITargetToExtent.objects.all()

    variables = RequestContext(request, {
        'asctarget_list': asctarget_list,
    })
    return render_to_response('services/iscsi_assoctargets.html', variables)

def iscsi_extents(request, objtype=None):
    extent_file_list = models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type='File')

    variables = RequestContext(request, {
        'extent_file_list': extent_file_list,
    })
    return render_to_response('services/iscsi_extents.html', variables)

def iscsi_dextents(request):
    extent_device_list = models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk')

    variables = RequestContext(request, {
        'extent_device_list': extent_device_list,
    })
    return render_to_response('services/iscsi_dextents.html', variables)

def iscsi_auth(request):
    target_auth_list = models.iSCSITargetAuthCredential.objects.all()

    variables = RequestContext(request, {
        'target_auth_list': target_auth_list,
    })
    return render_to_response('services/iscsi_auth.html', variables)

def iscsi_authini(request):
    auth_initiator_list = models.iSCSITargetAuthorizedInitiator.objects.all()

    variables = RequestContext(request, {
        'auth_initiator_list': auth_initiator_list,
    })
    return render_to_response('services/iscsi_authini.html', variables)

def iscsi_portals(request):
    iscsiportal_list = models.iSCSITargetPortal.objects.all()

    variables = RequestContext(request, {
        'iscsiportal_list': iscsiportal_list,
    })
    return render_to_response('services/iscsi_portals.html', variables)

"""TODO: This should be rewritten in a better way."""
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
        'ad_toggle' : 'activedirectory',
        'ldap_toggle' : 'ldap',
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
    if changing_service == "ldap" or changing_service == "activedirectory":
        if svc_entry.srv_enable == 1:
            notifier().start(changing_service)
            return HttpResponseRedirect('/freenas/media/images/ui/buttons/on.png')
        else:
            notifier().stop(changing_service)
            return HttpResponseRedirect('/freenas/media/images/ui/buttons/off.png')

    notifier().restart(changing_service)
    if svc_entry.srv_enable == 1:
        return HttpResponseRedirect('/freenas/media/images/ui/buttons/on.png')
    else:
        return HttpResponseRedirect('/freenas/media/images/ui/buttons/off.png')
