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
            # This is a debugging aid to raise exception when validation
            # is not passed.
            form.save()
    else:
        try:
            _entity = model.objects.order_by("-id").values()[0]
        except:
            # TODO: We throw an exception (which makes this try/except
            # meaningless) for now.  A future version will have the
            # ability to set up default values.
            raise
        form = theForm(data = _entity)
    variables = RequestContext(request, {
        'form': form
    })
    return render_to_response(url, variables)

def helperViewEm(request, theForm, model):
    data_saved = 0
    if request.method == 'POST':
        form = theForm(request.POST)
        if form.is_valid():
            # TODO: test if the data is the same as what is in the database?
            form.save()
            data_saved = 1
            if model.objects.count() > 3:
                stale_id = model.objects.order_by("-id")[3].id
                model.objects.filter(id__lte=stale_id).delete()
        else:
            pass
    else:
        try:
            _entity = model.objects.order_by("-id").values()[0]
        except:
            _entity = None
        form = theForm(data = _entity)
    return (data_saved, form)

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
    try:
        d = open('/etc/version.freenas', 'r')
        freenas_build = d.read()
        d.close()
    except:
        freenas_build = "Unrecognized build (/etc/version.freenas missing?)"
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
def NetworkView(request):
    interfaceMGMT = networkInterfaceMGMTForm(request.POST)
    vlan = networkVLANForm(request.POST)
    lagg = networkLAGGForm(request.POST)
    staticroute = networkStaticRouteForm(request.POST)
    if request.method == 'POST':
        if interfaceMGMT.is_valid():
            interfaceMGMT.save()
        if vlan.is_valid():
            vlan.save()
        if lagg.is_valid():
            lagg.save()
        if staticroute.is_valid():
            staticroute.save()
        return HttpResponseRedirect('/freenas/network/')
    else:
        interfaceMGMT = networkInterfaceMGMTForm()
        vlan = networkVLANForm()
        lagg = networkLAGGForm()
        staticroute = networkStaticRouteForm()
    variables = RequestContext(request, {
        'interfaceMGMT': interfaceMGMT,
        'vlan': vlan,
        'lagg': lagg,
        'staticroute': staticroute,
    })
    return render_to_response('freenas/network/index.html', variables)


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
def DiskView(request, template_name = 'freenas/disks/index.html'):
    disk = DiskForm(request.POST)
    diskgroup = DiskGroupForm(request.POST)
    volume = VolumeForm(request.POST)
    mountpoint = MountPointForm(request.POST)
    if request.method == 'POST':
        if disk.is_valid():
            disk.save()
        if diskgroup.is_valid():
            diskgroup.save()
        if volume.is_valid():
            volume.save()
        if mountpoint.is_valid():
            mountpoint.save()
        return HttpResponseRedirect('/freenas/disk/management/')
    else:
        disk_list = Disk.objects.all()
        group_list = DiskGroup.objects.all()
        volume_list = Volume.objects.all()
        disk = DiskForm()
        diskgroup = DiskGroupForm()
        volume = VolumeForm()
        mountpoint = MountPointForm()
    variables = RequestContext(request, {
        'disk_list': disk_list,
        'group_list': group_list,
        'volume_list': volume_list,
        'disk': disk,
        'diskgroup': diskgroup,
        'volume': volume,
        'mountpoint': mountpoint,
    })
    return render_to_response('freenas/disks/index.html', variables)


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


@login_required
def SharesView(request):
    windowsshare = WindowsShareForm(request.POST)
    appleshare = AppleShareForm(request.POST)
    unixshare = UnixShareForm(request.POST)
    if request.method == 'POST':
        if windowsshare.is_valid():
            windowsshare.save()
        if appleshare.is_valid():
            appleshare.save()
        if unixshare.is_valid():
            unixshare.save()
        return HttpResponseRedirect('/freenas/shares/')
    else:
        windowsshare = WindowsShareForm()
        appleshare = AppleShareForm()
        unixshare = UnixShareForm()
    variables = RequestContext(request, {
        'windowsshare': windowsshare,
        'appleshare': appleshare,
        'unixshare': unixshare,
        })
    return render_to_response('freenas/shares/index.html', variables)

## Services section

@login_required
def ServicesView(request):
    # Counter for forms we have validated.
    forms_saved = 0
    saved, cifs_form = helperViewEm(request, servicesCIFSForm, servicesCIFS)
    forms_saved = forms_saved + saved
    saved, afp_form = helperViewEm(request, servicesAFPForm, servicesAFP)
    forms_saved = forms_saved + saved
    saved, nfs_form = helperViewEm(request, servicesNFSForm, servicesNFS)
    forms_saved = forms_saved + saved
    saved, rsync_form = helperViewEm(request, servicesRSYNCForm, servicesRSYNC)
    forms_saved = forms_saved + saved
    saved, unison_form = helperViewEm(request, servicesUnisonForm, servicesUnison)
    forms_saved = forms_saved + saved
    saved, iscsi_form = helperViewEm(request, servicesiSCSITargetForm, servicesiSCSITarget)
    forms_saved = forms_saved + saved
    saved, dynamicdns_form = helperViewEm(request, servicesDynamicDNSForm, servicesDynamicDNS)
    forms_saved = forms_saved + saved
    saved, snmp_form = helperViewEm(request, servicesSNMPForm, servicesSNMP)
    forms_saved = forms_saved + saved
    saved, ups_form = helperViewEm(request, servicesUPSForm, servicesUPS)
    forms_saved = forms_saved + saved
    saved, webserver_form = helperViewEm(request, servicesWebserverForm, servicesWebserver)
    forms_saved = forms_saved + saved
    saved, bittorrent_form = helperViewEm(request, servicesBitTorrentForm, servicesBitTorrent)
    forms_saved = forms_saved + saved
    saved, ftp_form = helperViewEm(request, servicesFTPForm, servicesFTP)
    forms_saved = forms_saved + saved
    saved, tftp_form = helperViewEm(request, servicesTFTPForm, servicesTFTP)
    forms_saved = forms_saved + saved
    saved, ssh_form = helperViewEm(request, servicesSSHForm, servicesSSH)
    forms_saved = forms_saved + saved
    
    if request.method == 'POST':
        if forms_saved > 0:
            return HttpResponseRedirect('/freenas/services/')
        else:
            pass # Need to raise a validation exception
    else:
        variables = RequestContext(request, {
            'cifs': cifs_form,
            'afp': afp_form,
            'nfs': nfs_form,
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
def AccessView(request):
    ldap = accessLDAPForm(request.POST)
    activedirectory = accessActiveDirectoryForm(request.POST)
    if request.method == 'POST':
        if ldap.is_valid():
            ldap.save()
        return HttpResponseRedirect('/freenas/access/')
    if request.method == 'POST':
        if activedirectory.is_valid():
            activedirectory.save()
        return HttpResponseRedirect('/freenas/access/')
    else:
        ldap = accessLDAPForm()
        activedirectory = accessActiveDirectoryForm()
    variables = RequestContext(request, {
        'ldap': ldap,
        'activedirectory': activedirectory,
    })
    return render_to_response('freenas/access/index.html', variables)
