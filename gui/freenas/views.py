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
from freenasUI.freenas.models import Disk, Volume, networkStaticRoute
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
import os, commands

def helperView(request, theForm, model, url):
    if request.method == 'POST':
        form = theForm(request.POST)
        if form.is_valid():
            form.save()
            if model.objects.count() > 3:
                stale_id = model.objects.order_by("-id")[3].id
                model.objects.filter(id__lte=stale_id).delete()
    else:
        _entity = model.objects.order_by("-id").values()[0]
        form = theForm(data = _entity)
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response(url, variables)

## Generic Views for GUI Screens 
@login_required
def index(request):
    hostname = commands.getoutput("hostname")
    uname1 = os.uname()[0]
    uname2 = os.uname()[2]
    platform = os.popen("sysctl -n hw.model").read()
    date = os.popen('date').read()
    uptime = commands.getoutput("uptime | awk -F', load averages:' '{ print $1 }'")
    loadavg = commands.getoutput("uptime | awk -F'load averages:' '{ print $2 }'")
    top = os.popen('top').read()
    d = open('/etc/version.freenas', 'r')
    freenas_build = d.read()
    d.close()
    variables = RequestContext(request, {
        'hostname': hostname,
        'uname1': uname1,
        'uname2': uname2,
        'platform': platform,
        'date': date,
        'uptime': uptime,
        'loadavg': loadavg,
        'top': top,
        'freenas_build': freenas_build,
    })  
    return render_to_response('freenas/index.html', variables)

@login_required
def statusProcessesView(request):
    top = os.popen('top').read()
    variables = RequestContext(request, {
        'top': top,
    })  
    return render_to_response('freenas/status/processes.html', variables)


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

@login_required
def systemReboot(request):
    """ reboots the system """
    notifier().restart("system")
    return render_to_response('freenas/system/reboot.html')

@login_required
def systemShutdown(request):
    """ shuts down the system and powers off the system """
    notifier().stop("system")
    return render_to_response('freenas/system/shutdown.html')

@login_required
def systemGeneralSetupView(request):
    return helperView(request, systemGeneralSetupForm, systemGeneralSetup, 'freenas/system/general_setup.html')

@login_required
def systemGeneralPasswordView(request):
    return helperView(request, systemGeneralPasswordForm, systemGeneralPassword, 'freenas/system/general_password.html')

@login_required
def systemAdvancedView(request):
    return helperView(request, systemAdvancedForm, systemAdvanced, 'freenas/system/advanced.html')

@login_required
def systemAdvancedEmailView(request):
    return helperView(request, systemAdvancedEmailForm, systemAdvancedEmail, 'freenas/system/advanced_email.html')

@login_required
def systemAdvancedProxyView(request):
    return helperView(request, systemAdvancedProxyForm, systemAdvancedProxy, 'freenas/system/advanced_proxy.html')

@login_required
def systemAdvancedSwapView(request):
    return helperView(request, systemAdvancedSwapForm, systemAdvancedSwap, 'freenas/system/advanced_swap.html')

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
def staticroutes_add_wrapper(request, *args, **kwargs):
    wiz = StaticRouteWizard([networkStaticRouteForm])
    return wiz(request, *args, **kwargs)

@login_required
def staticroutes_list(request, template_name='freenas/network/staticroute_list.html'):
    query_set = networkStaticRoute.objects.all()
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )

@login_required
def staticroute_detail(request, staticrouteid, template_name='freenas/network/staticroute_detail.html'):
    return object_detail(
        request,
        template_name = template_name,
        object_id = staticrouteid,
        queryset = networkStaticRoute.objects.all(),
    ) 


## Disk section
@login_required
def disk_add(request):
    if request.method == 'POST':
        form = DiskForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('/freenas/disk/management/disks/')
    else:
        form = DiskForm()
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response('freenas/disks/disk_add.html', variables)

@login_required
def disk_add_wrapper(request, *args, **kwargs):
    wiz = DiskWizard([DiskAdvancedForm])
    return wiz(request, *args, **kwargs)

@login_required
def disk_list(request, template_name='freenas/disks/disk_list.html'):
    query_set = Disk.objects.all()
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )

@login_required
def disk_detail(request, diskid, template_name='freenas/disks/disk_detail.html'):
    return object_detail(
        request,
        template_name = template_name,
        object_id = diskid,
        queryset = Disk.objects.all(),
    ) 



@login_required
def diskgroup_add_wrapper(request, *args, **kwargs):
    wiz = DiskGroupWizard([DiskGroupForm])
    return wiz(request, *args, **kwargs)

@login_required
def diskgroup_list(request, template_name='freenas/disks/groups/diskgroup_list.html'):
    query_set = DiskGroup.objects.values().order_by('name')
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )

@login_required
def diskgroup_detail(request, diskgroupid, template_name='freenas/disks/groups/diskgroup_detail.html'):
    return object_detail(
        request,
        template_name = template_name,
        object_id = diskgroupid,
        queryset = DiskGroup.objects.all(),
    ) 



@login_required
def volume_create_wrapper(request, *args, **kwargs):
    wiz = VolumeWizard([VolumeForm])
    return wiz(request, *args, **kwargs)

@login_required
def volume_list(request, template_name='freenas/disks/volumes/volume_list.html'):
    query_set = Volume.objects.values().order_by('groups')
    #if len(query_set) == 0:
    #    raise Http404()
    return object_list(
        request,
        template_name = template_name,
        queryset = query_set
    )

@login_required
def volume_detail(request, volumeid, template_name='freenas/disks/volumes/volume_detail.html'):
    return object_detail(
        request,
        template_name = template_name,
        object_id = volumeid,
        queryset = Volume.objects.all(),
    ) 


""" Shares """
@login_required
def SharesView(request):
    mountpoint_form = MountPointForm(request.POST)
    cifs_form = servicesCIFSForm(request.POST)
    afp_form = servicesAFPForm(request.POST)
    nfs_form = servicesNFSForm(request.POST)
    windowsshare_form = WindowsShareForm(request.POST)
    appleshare_form = AppleShareForm(request.POST)
    unixshare_form = UnixShareForm(request.POST)
    if request.method == 'POST':
        if mountpoint_form.is_valid() and cifs_form.is_valid() and afp_form.is_valid() and nfs_form.is_valid() and windowsshare_form.is_valid() and appleshare_form.is_valid() and unixshare_form.is_valid():
            mountpoint_form.save()
            cifs_form.save()
            afp_form.save()
            nfs_form.save()
            windowsshare_form.save()
            appleshare_form.save()
            unixshare_form.save()
            return HttpResponseRedirect('/freenas/shares/')
    else:
        mountpoint_form = MountPointForm()
        cifs_form = servicesCIFSForm()
        afp_form = servicesAFPForm()
        nfs_form = servicesNFSForm()
        windowsshare_form = WindowsShareForm()
        appleshare_form = AppleShareForm()
        unixshare_form = UnixShareForm()
    variables = RequestContext(request, {
        'mountpoint_form': mountpoint_form,
        'cifs_form': cifs_form,
        'afp_form': afp_form,
        'nfs_form': nfs_form,
        'windowsshare_form': nfs_form,
        'appleshare_form': nfs_form,
        'unix_form': nfs_form,
    })
    return render_to_response('freenas/shares/index.html', variables)

## Services section

@login_required
def ServicesView(request):
    rsync_form = servicesRSYNCForm(request.POST)
    unison_form = servicesUnisonForm(request.POST)
    iscsi_form = servicesiSCSITargetForm(request.POST)
    dynamicdns_form = servicesDynamicDNSForm(request.POST)
    snmp_form = servicesSNMPForm(request.POST)
    ups_form = servicesUPSForm(request.POST)
    webserver_form = servicesWebserverForm(request.POST)
    bittorrent_form = servicesBitTorrentForm(request.POST)
    ftp_form = servicesFTPForm(request.POST)
    tftp_form = servicesTFTPForm(request.POST)
    ssh_form = servicesSSHForm(request.POST)
    if request.method == 'POST':
        if rsync_form.is_valid():
            rsync_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if unison_form.is_valid():
            unison_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if iscsi_form.is_valid():
            iscsi_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if dynamicdns_form.is_valid(): 
            dynamicdns_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if snmp_form.is_valid():
            snmp_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if ups_form.is_valid():
            ups_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if webserver_form.is_valid(): 
            webserver_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if bittorrent_form.is_valid(): 
            bittorrent_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if ftp_form.is_valid():
            ftp_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if tftp_form.is_valid():
            tftp_form.save()
        return HttpResponseRedirect('/freenas/services/')
    if request.method == 'POST':
        if ssh_form.is_valid():
            ssh_form.save()
        return HttpResponseRedirect('/freenas/services/')
    else:
        rsync_form = servicesRSYNCForm()
        unison_form = servicesUnisonForm()
        iscsi_form = servicesiSCSITargetForm()
        dynamicdns_form = servicesDynamicDNSForm()
        snmp_form = servicesSNMPForm()
        ups_form = servicesUPSForm()
        webserver_form = servicesWebserverForm()
        bittorrent_form = servicesBitTorrentForm()
        ftp_form = servicesFTPForm()
        tftp_form = servicesTFTPForm()
        ssh_form = servicesSSHForm()
    variables = RequestContext(request, {
        'rsync_form': rsync_form,
        'unison_form': unison_form,
        'iscsi_form': iscsi_form,
        'dynamicdns_form': dynamicdns_form,
        'snmp_form': snmp_form,
        'ups_form': ups_form,
        'webserver_form': webserver_form,
        'bittorrent_form': bittorrent_form,
        'ftp_form': ftp_form,
        'tftp_form': tftp_form,
        'ssh_form': ssh_form,
    })
    return render_to_response('freenas/services/index.html', variables)

@login_required
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

@login_required
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

@login_required
def accessActiveDirectoryView(request):
    return helperView(request, accessActiveDirectoryForm, accessActiveDirectory, 'freenas/access/active_directory.html')

@login_required
def accessLDAPView(request):
    return helperView(request, accessLDAPForm, accessLDAP, 'freenas/access/ldap.html')
