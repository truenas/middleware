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

from freenasUI.freenas.forms import * 
from freenasUI.freenas.models import * 
from freenasUI.freenas.models import Disk, Volume
from django.forms.models import modelformset_factory
from django.contrib.auth.decorators import permission_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.contrib.auth import authenticate, login, logout
from django.template import RequestContext
from django.http import Http404
from django.views.generic.list_detail import object_detail, object_list

## Generic Views for GUI Screens 

def login(request):
    username = request.POST['username']
    password = request.POST['password']
    user = authenticate(username=username, password=password)
    if user is not None:
        if user.is_active:
            login(request, user)
            # Redirect to a success page.
        return HttpResponseRedirect('/freenas/login/') # Redirect after POST

def logout(request):
    logout(request)
    # Redirect to a success page.
    return HttpResponseRedirect('/freenas/logout/') # Redirect after POST

## System Section
def systemGeneralSetupView(request):
    if request.method == 'POST':
        form = systemGeneralSetupForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        try:
            _entity = systemGeneralSetup.objects.filter(pk=True).values()[0]
        except:
            _entity = {}
        form = systemGeneralSetupForm(data = _entity)
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/general_setup.html', variables)


def systemGeneralPasswordView(request):
    if request.method == 'POST':
        form = systemGeneralPasswordForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemGeneralPasswordForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/general_password.html', variables)

def systemAdvancedView(request):
    if request.method == 'POST':
        form = systemAdvancedForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced.html', variables)

def systemAdvancedEmailView(request):
    if request.method == 'POST':
        form = systemAdvancedEmailForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedEmailForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced_email.html', variables)

def systemAdvancedProxyView(request):
    if request.method == 'POST':
        form = systemAdvancedProxyForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedProxyForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced_proxy.html', variables)

def systemAdvancedSwapView(request):
    if request.method == 'POST':
        form = systemAdvancedSwapForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedSwapForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced_swap.html', variables)

def CommandScriptsView(request):
    if request.method == 'POST':
        form = CommandScriptsForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = CommandScriptsForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/commandscripts_add.html', variables)

def systemAdvancedCommandScriptsView(request):
    if request.method == 'POST':
        form = systemAdvancedCommandScriptsForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedCommandScriptsForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced_commandscripts.html', variables)

def systemAdvancedCronView(request):
    if request.method == 'POST':
        form = systemAdvancedCronForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedCronForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced_cron.html', variables)

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

def rcconfView(request):
    if request.method == 'POST':
        form = rcconfForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = rcconfForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/rcconf.html', variables)

def systemAdvancedRCconfView(request):
    if request.method == 'POST':
        form = systemAdvancedRCconfForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedRCconfForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced_rcconf.html', variables)

def sysctlMIBView(request):
    if request.method == 'POST':
        form = sysctlMIBForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = sysctlMIBForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/sysctlMIB.html', variables)

def systemAdvancedSYSCTLconfView(request):
    if request.method == 'POST':
        form = systemAdvancedSYSCTLconfForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = systemAdvancedSYSCTLconfForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/system/advanced_sysctlconf.html', variables)

## Network Section

def networkInterfaceMGMTView(request):
    if request.method == 'POST':
        form = networkInterfaceMGMTForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = networkInterfaceMGMTForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/interfaces.html', variables)

def networkVLANView(request):
    if request.method == 'POST':
        form = networkVLANForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = networkVLANForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/vlan_add.html', variables)

def networkInterfaceMGMTvlanView(request):
    if request.method == 'POST':
        form = networkInterfaceMGMTvlanForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = networkInterfaceMGMTvlanForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/vlan.html', variables)

def networkLAGGView(request):
    if request.method == 'POST':
        form = networkLAGGForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = networkLAGGForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/lagg_add.html', variables)

def networkInterfaceMGMTlaggView(request):
    if request.method == 'POST':
        form = networkInterfaceMGMTlaggForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = networkInterfaceMGMTlaggForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/lagg.html', variables)

def networkHostsView(request):
    if request.method == 'POST':
        form = networkHostsForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = networkHostsForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/hosts.html', variables)

def networkStaticRoutesView(request):
    if request.method == 'POST':
        form = networkStaticRoutesForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = networkStaticRoutesForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/staticroutes.html', variables)

def StaticRoutesView(request):
    if request.method == 'POST':
        form = StaticRoutesForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = StaticRoutesForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/network/staticroutes_add.html', variables)

## Disk section


def disk_detail(request, diskid, template_name='freenas/disks/disk_detail.html'):

    return object_detail(
        request,
        template_name = template_name,
        object_id = diskid,
        queryset = Disk.objects.all(),
    ) 


def disk_list(request, template_name='freenas/disks/disk_list.html'):
    query_set = Disk.objects.all()
    if len(query_set) == 0:
        raise Http404()
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )

def volume_detail(request, volumeid, template_name='freenas/disks/volume_detail.html'):

    return object_detail(
        request,
        template_name = template_name,
        object_id = volumeid,
        queryset = Volume.objects.all(),
    ) 


def volume_list(request, template_name='freenas/disks/volume_list.html'):
    query_set = Volume_group.objects.all()
    if len(query_set) == 0:
        raise Http404()
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )


def DiskManagerView(request):
    if request.method == 'POST':
        form = DiskManagerForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = DiskManagerForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/disks/disk_manager.html', variables)

def DiskView(request):
    if request.method == 'POST':
        form = DiskForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = DiskForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/disks/disk.html', variables)

def DiskGroupView(request):
    if request.method == 'POST':
        form = DiskGroupForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = DiskGroupForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/disks/disk_group.html', variables)

def VolumeView(request):
    if request.method == 'POST':
        form = VolumeForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = VolumeForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/disks/disk_volume.html', variables)


def DiskAdvancedView(request):
    if request.method == 'POST':
        form = DiskAdvancedForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = DiskAdvancedForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/disks/disk_advanced.html', variables)

#def diskMGMTView(request):
#    if request.method == 'POST':
#        form = diskMGMTForm(request.POST)
#        if form.is_valid():
#            form.save()
#    else:
#        form = diskMGMTForm()
#    variables = RequestContext(request, {
#        'form': form
#    })
 #   return render_to_response('freenas/disks/disks.html', variables)

## Services section

def servicesCIFSView(request):
    if request.method == 'POST':
        form = servicesCIFSForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesCIFSForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/cifs_settings.html', variables)

def shareCIFSView(request):
    if request.method == 'POST':
        form = shareCIFSForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = shareCIFSForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/cifs_shares_add.html', variables)

def servicesCIFSshareView(request):
    if request.method == 'POST':
        form = servicesCIFSshareForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesCIFSshareForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/cifs_shares.html', variables)

def servicesFTPView(request):
    if request.method == 'POST':
        form = servicesFTPForm(request.POST)
        if form.is_valid():
            form.save()
            if servicesFTP.objects.count() > 3:
                try:
                    stale_id = servicesFTP.objects.order_by("-id")[3].id
                    servicesFTP.objects.filter(id__lte=stale_id).delete()
                except:
                    pass
    else:
        try:
            _entity = servicesFTP.objects.order_by("-id").values()[0]
        except:
            _entity = {}
        form = servicesFTPForm(data = _entity)
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/ftp.html', variables)

def servicesTFTPView(request):
    if request.method == 'POST':
        form = servicesTFTPForm(request.POST)
        if form.is_valid():
            form.save()
            if servicesTFTP.objects.count() > 3:
                try:
                    stale_id = servicesTFTP.objects.order_by("-id")[3].id
                    servicesTFTP.objects.filter(id__lte=stale_id).delete()
                except:
                    pass
    else:
        try:
            _entity = servicesTFTP.objects.order_by("-id").values()[0]
        except:
            _entity = {}
        form = servicesTFTPForm(data = _entity)
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/tftp.html', variables)

def servicesSSHView(request):
    if request.method == 'POST':
        form = servicesSSHForm(request.POST)
        if form.is_valid():
            form.save()
            if servicesSSH.objects.count() > 3:
                try:
                    stale_id = servicesSSH.objects.order_by("-id")[3].id
                    servicesSSH.objects.filter(id__lte=stale_id).delete()
                except:
                    pass
    else:
        try:
            _entity = servicesSSH.objects.order_by("-id").values()[0]
        except:
            _entity = {}
        form = servicesSSHForm(data = _entity)
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/ssh.html', variables)

def servicesNFSView(request):
    if request.method == 'POST':
        form = servicesNFSForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesNFSForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/nfs.html', variables)

def shareNFSView(request):
    if request.method == 'POST':
        form = shareNFSForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = shareNFSForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/nfs_add_share.html', variables)

def servicesNFSshareView(request):
    if request.method == 'POST':
        form = servicesNFSshareForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesNFSshareForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/nfs_shares.html', variables)

def servicesAFPView(request):
    if request.method == 'POST':
        form = servicesAFPForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesAFPForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/afp.html', variables)

def shareAFPView(request):
    if request.method == 'POST':
        form = shareAFPForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = shareAFPForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/afp_add_share.html', variables)

def servicesAFPshareView(request):
    if request.method == 'POST':
        form = servicesAFPshareForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesAFPshareForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/afp_shares.html', variables)

def clientrsyncjobView(request):
    if request.method == 'POST':
        form = clientrsyncjobForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = clientrsyncjobForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/rsync_clientjob.html', variables)

def localrsyncjobView(request):
    if request.method == 'POST':
        form = localrsyncjobForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = localrsyncjobForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/rsync_localjob.html', variables)

def servicesRSYNCView(request):
    if request.method == 'POST':
        form = servicesRSYNCForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesRSYNCForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/rsync.html', variables)

def servicesUnisonView(request):
    if request.method == 'POST':
        form = servicesUnisonForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesUnisonForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/unison.html', variables)

def servicesiSCSITargetView(request):
    if request.method == 'POST':
        form = servicesiSCSITargetForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesiSCSITargetForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/iscsi_target.html', variables)

def servicesDynamicDNSView(request):
    if request.method == 'POST':
        form = servicesDynamicDNSForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesDynamicDNSForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/dyndns.html', variables)

def servicesSNMPView(request):
    if request.method == 'POST':
        form = servicesSNMPForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesSNMPForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/snmp.html', variables)

def servicesUPSView(request):
    if request.method == 'POST':
        form = servicesUPSForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesUPSForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/ups.html', variables)

def servicesWebserverView(request):
    if request.method == 'POST':
        form = servicesWebserverForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesWebserverForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/webserver.html', variables)

def servicesBitTorrentView(request):
    if request.method == 'POST':
        form = servicesBitTorrentForm(request.POST)
        if form.is_valid():
            form.save()
    else:
        form = servicesBitTorrentForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/services/bittorrent.html', variables)
