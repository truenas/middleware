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
from freenasUI.middleware.notifier import notifier
from freenasUI.common.helperview import helperViewEm
import os, commands

@login_required
def cronjobView(request):
    if request.method == 'POST':
        form = cronjobForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = cronjobForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/cronjob.html', variables)

## Services section

@login_required
def services(request):
    # Counter for forms we have validated.
    forms_saved = 0
    saved, cifs = helperViewEm(request, CIFSForm, CIFS)
    forms_saved = forms_saved + saved
    saved, afp = helperViewEm(request, AFPForm, AFP)
    forms_saved = forms_saved + saved
    saved, nfs = helperViewEm(request, NFSForm, NFS)
    forms_saved = forms_saved + saved
    saved, rsync = helperViewEm(request, rsyncjobForm, rsyncjob)
    forms_saved = forms_saved + saved
    saved, unison = helperViewEm(request, UnisonForm, Unison)
    forms_saved = forms_saved + saved
    saved, iscsi = helperViewEm(request, iSCSITargetForm, iSCSITarget)
    forms_saved = forms_saved + saved
    saved, dynamicdns = helperViewEm(request, DynamicDNSForm, DynamicDNS)
    forms_saved = forms_saved + saved
    saved, snmp = helperViewEm(request, SNMPForm, SNMP)
    forms_saved = forms_saved + saved
    saved, ups = helperViewEm(request, UPSForm, UPS)
    forms_saved = forms_saved + saved
    saved, webserver = helperViewEm(request, WebserverForm, Webserver)
    forms_saved = forms_saved + saved
    saved, bittorrent = helperViewEm(request, BitTorrentForm, BitTorrent)
    forms_saved = forms_saved + saved
    saved, ftp = helperViewEm(request, FTPForm, FTP)
    forms_saved = forms_saved + saved
    saved, tftp = helperViewEm(request, TFTPForm, TFTP)
    forms_saved = forms_saved + saved
    saved, ssh = helperViewEm(request, SSHForm, SSH)
    forms_saved = forms_saved + saved
    saved, activedirectory = helperViewEm(request, ActiveDirectoryForm, ActiveDirectory)
    forms_saved = forms_saved + saved
    saved, ldap = helperViewEm(request, LDAPForm, LDAP)
    forms_saved = forms_saved + saved
    
    if request.method == 'POST':
        srv = Services.objects.all()
        if forms_saved > 0:
            return HttpResponseRedirect('/services/')
        else:
            pass # Need to raise a validation exception
    else:
        srv = Services.objects.all()
        variables = RequestContext(request, {
            'srv': srv,
            'cifs': cifs,
            'afp': afp,
            'nfs': nfs,
            'rsync': rsync,
            'unison': unison,
            'iscsi': iscsi,
            'dynamicdns': dynamicdns,
            'snmp': snmp,
            'ups': ups,
            'webserver': webserver,
            'bittorrent': bittorrent,
            'ftp': ftp,
            'tftp': tftp,
            'ssh': ssh,
            'activedirectory': activedirectory,
            'ldap': ldap,
            })
        return render_to_response('freenas/services/index.html', variables)

"""TODO: This should be rewritten in a better way."""
@login_required
def servicesToggleView(request, formname):
    form2namemap = {
	'cifs_toggle' : 'cifs',
	'afp_toggle' : 'afp',
	'nfs_toggle' : 'nfs',
	'unison_toggle' : 'unison',
	'iscsi_toggle' : 'iscsi',
	'dyndns_toggle' : 'dyndns',
	'snmp_toggle' : 'snmp',
	'ups_toggle' : 'ups',
	'bt_toggle' : 'bittorrent',
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
    svc_entry = Services.objects.get(srv_service=changing_service)
    if svc_entry.srv_enable:
	svc_entry.srv_enable = 0
    else:
	svc_entry.srv_enable = 1
    svc_entry.save()
    # forcestop then start to make sure the service is of the same
    # status.
    notifier().restart(changing_service)
    return HttpResponseRedirect('/services/')

