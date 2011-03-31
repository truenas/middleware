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

from freenasUI.services.forms import * 
from freenasUI.services.models import services as Services 
from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404
from django.views.generic.list_detail import object_detail, object_list
from django.views.generic.create_update import update_object, delete_object
from freenasUI.middleware.notifier import notifier
from freenasUI.common.helperview import helperViewEx, helperViewEmpty
import os, commands


@login_required
def home(request):

    try:
        cifs = CIFS.objects.order_by("-id")[0]
    except IndexError:
        cifs = None

    try:
        afp = AFP.objects.order_by("-id")[0]
    except IndexError:
        afp = None

    try:
        nfs = NFS.objects.order_by("-id")[0]
    except IndexError:
        nfs = None

    try:
        dynamicdns = DynamicDNS.objects.order_by("-id")[0]
    except IndexError:
        dynamicdns = None

    try:
        snmp = SNMP.objects.order_by("-id")[0]
    except IndexError:
        snmp = None

    try:
        ftp = FTP.objects.order_by("-id")[0]
    except IndexError:
        ftp = None

    try:
        tftp = TFTP.objects.order_by("-id")[0]
    except IndexError:
        tftp = None

    try:
        ssh = SSH.objects.order_by("-id")[0]
    except IndexError:
        ssh = None

    try:
        activedirectory = ActiveDirectory.objects.order_by("-id")[0]
    except IndexError:
        activedirectory = None

    try:
        ldap = LDAP.objects.order_by("-id")[0]
    except IndexError:
        ldap = None

    srv = Services.objects.all()
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

@login_required
def services(request, objtype=None):

    if objtype != None:
        focus_form = objtype
    else:
        focus_form = None 
    srv = Services.objects.all()
    target_list = iSCSITarget.objects.all()
    extent_device_list = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk')
    extent_file_list = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='File')
    asctarget_list = iSCSITargetToExtent.objects.all()
    target_auth_list = iSCSITargetAuthCredential.objects.all()
    auth_initiator_list = iSCSITargetAuthorizedInitiator.objects.all()
    iscsiportal_list = iSCSITargetPortal.objects.all()

    cifs = helperViewEx(request, CIFSForm, CIFS, objtype, 'cifs')
    afp = helperViewEx(request, AFPForm, AFP, objtype, 'afp')
    nfs = helperViewEx(request, NFSForm, NFS, objtype, 'nfs')
    istgtglobal = helperViewEx(request, iSCSITargetGlobalConfigurationForm, iSCSITargetGlobalConfiguration, objtype, 'istgtglobal')
    snmp = helperViewEx(request, SNMPForm, SNMP, objtype, 'snmp')
    ftp = helperViewEx(request, FTPForm, FTP, objtype, 'ftp')
    tftp = helperViewEx(request, TFTPForm, TFTP, objtype, 'tftp')
    ssh = helperViewEx(request, SSHForm, SSH, objtype, 'ssh')
    activedirectory = helperViewEx(request, ActiveDirectoryForm, ActiveDirectory, objtype, 'activedirectory')
    dynamicdns = helperViewEx(request, DynamicDNSForm, DynamicDNS, objtype, 'dynamicdns')
    ldap = helperViewEx(request, LDAPForm, LDAP, objtype, 'ldap')
    iscsitarget = helperViewEmpty(request, iSCSITargetForm, objtype, 'iscsitarget')
    iscsiextentfile = helperViewEmpty(request, iSCSITargetFileExtentForm, objtype, 'iscsiextentfile', prefix="fe")
    iscsiextentdevice = helperViewEmpty(request, iSCSITargetDeviceExtentForm, objtype, 'iscsiextentdevice', prefix="de")
    asctarget = helperViewEmpty(request, iSCSITargetToExtentForm, objtype, 'asctarget')
    target_auth = helperViewEmpty(request, iSCSITargetAuthCredentialForm, objtype, 'target_auth')
    auth_initiator = helperViewEmpty(request, iSCSITargetAuthorizedInitiatorForm, objtype, 'auth_initiator')
    iscsiportal = helperViewEmpty(request, iSCSITargetPortalForm, objtype, 'iscsiportal')

    variables = RequestContext(request, {
        'focused_tab' : 'services',
        'srv': srv,
        'cifs': cifs,
        'dynamicdns': dynamicdns,
        'afp': afp,
        'nfs': nfs,
        'istgtglobal': istgtglobal,
        'snmp': snmp,
        'ftp': ftp,
        'tftp': tftp,
        'ssh': ssh,
        'activedirectory': activedirectory,
        'ldap': ldap,
        'iscsitarget': iscsitarget,
        'target_list': target_list,
        'iscsiextentfile': iscsiextentfile,
        'iscsiextentdevice': iscsiextentdevice,
        'extent_file_list': extent_file_list,
        'extent_device_list': extent_device_list,
        'extent_file_list': extent_file_list,
        'asctarget': asctarget,
        'asctarget_list': asctarget_list,
        'target_auth': target_auth,
        'target_auth_list': target_auth_list,
        'auth_initiator': auth_initiator,
        'auth_initiator_list': auth_initiator_list,
        'iscsiportal': iscsiportal,
        'iscsiportal_list': iscsiportal_list,
        'focus_form': focus_form,
        })
    return render_to_response('services/index.html', variables)


@login_required
def iscsi(request):
    gconfid = iSCSITargetGlobalConfiguration.objects.all().order_by("-id")[0].id
    variables = RequestContext(request, {
        'focus_tab' : request.GET.get('tab',''),
        'gconfid': gconfid,
        })
    return render_to_response('services/iscsi.html', variables)

@login_required
def iscsi_targets(request):
    target_list = iSCSITarget.objects.all()

    variables = RequestContext(request, {
        'target_list': target_list,
    })
    return render_to_response('services/iscsi_targets.html', variables)

@login_required
def iscsi_assoctargets(request, objtype=None):
    asctarget_list = iSCSITargetToExtent.objects.all()

    variables = RequestContext(request, {
        'asctarget_list': asctarget_list,
    })
    return render_to_response('services/iscsi_assoctargets.html', variables)

@login_required
def iscsi_extents(request, objtype=None):
    extent_file_list = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='File')

    variables = RequestContext(request, {
        'extent_file_list': extent_file_list,
    })
    return render_to_response('services/iscsi_extents.html', variables)

@login_required
def iscsi_dextents(request):
    extent_device_list = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk')

    variables = RequestContext(request, {
        'extent_device_list': extent_device_list,
    })
    return render_to_response('services/iscsi_dextents.html', variables)

@login_required
def iscsi_auth(request):
    target_auth_list = iSCSITargetAuthCredential.objects.all()

    variables = RequestContext(request, {
        'target_auth_list': target_auth_list,
    })
    return render_to_response('services/iscsi_auth.html', variables)

@login_required
def iscsi_authini(request):
    auth_initiator_list = iSCSITargetAuthorizedInitiator.objects.all()

    variables = RequestContext(request, {
        'auth_initiator_list': auth_initiator_list,
    })
    return render_to_response('services/iscsi_authini.html', variables)

@login_required
def iscsi_portals(request):
    iscsiportal_list = iSCSITargetPortal.objects.all()

    variables = RequestContext(request, {
        'iscsiportal_list': iscsiportal_list,
    })
    return render_to_response('services/iscsi_portals.html', variables)

"""TODO: This should be rewritten in a better way."""
@login_required
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
    svc_entry = Services.objects.get(srv_service=changing_service)
    if opposing_service:
        opp_svc_entry = Services.objects.get(srv_service=opposing_service)
    # Turning things off is always ok
    if svc_entry.srv_enable:
	svc_entry.srv_enable = 0
    else:
        if opposing_service and not opp_svc_entry.srv_enable == 1 or not opposing_service:
	    svc_entry.srv_enable = 1
    svc_entry.save()
    # forcestop then start to make sure the service is of the same
    # status.
    notifier().restart(changing_service)
    if svc_entry.srv_enable == 1:
        return HttpResponseRedirect('/freenas/media/images/ui/buttons/on.png')
    else:
        return HttpResponseRedirect('/freenas/media/images/ui/buttons/off.png')

@login_required
def generic_delete(request, object_id, objtype):
    services_model_map = {
            'iscsitarget':    iSCSITarget,
            'iscsiextent':   iSCSITargetExtent,
            'asctarget':   iSCSITargetToExtent,
            'target_auth':   iSCSITargetAuthCredential,
            'iscsiportal':   iSCSITargetPortal,
            'auth_initiator':  iSCSITargetAuthorizedInitiator,
            'iscsiportal':   iSCSITargetPortal,
    }
    return delete_object(
        request = request,
        model = services_model_map[objtype],
        post_delete_redirect = '/services/', 
        object_id = object_id, 
        )

@login_required
def generic_update(request, object_id, objtype):
    objtype2form = {
            'iscsitarget':   ( iSCSITarget, iSCSITargetForm ),
            'iscsiextent':   ( iSCSITargetExtent, iSCSITargeExtentEditForm),
            'asctarget':   ( iSCSITargetToExtent, iSCSITargetToExtentForm ),
            'target_auth':   ( iSCSITargetAuthCredential, iSCSITargetAuthCredentialForm ),
            'iscsiportal':   ( iSCSITargetPortal, iSCSITargetPortalForm ),
            'auth_initiator':   ( iSCSITargetAuthorizedInitiator, iSCSITargetAuthorizedInitiatorForm ),
            'iscsiportal':   ( iSCSITargetPortal, iSCSITargetPortalForm ),
            } 
    model, form_class = objtype2form[objtype]
    return update_object(
        request = request,
        model = model, form_class = form_class,
        object_id = object_id, 
        post_save_redirect = '/services/' + objtype + '/view/',
        )

