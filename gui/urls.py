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

from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template
from django.views.generic import list_detail
from freenasUI.freenas.models import *
from freenasUI.freenas.models import Disk 
from freenasUI.freenas.forms import * 
from freenasUI.freenas.views import * 
import os, commands
admin.autodiscover()

##  FreeNAS GUI
##  System Information
##
##  The following is used by the template variables defined in freenas_info
##  Let's optimize this in the future, seems a bit messy and out of place
##

def hostname():
    return commands.getoutput("hostname") # displays hostname
#def version():
#    return freenas_version
def uname1():
    return os.uname()[0] # displays operating system name, eg; FreeBSD
def uname2():
    return os.uname()[2] # diplays release info, eg; 7.1-RELEASE
def platform():
    return os.popen("sysctl -n hw.model").read() # displays cpu info
#    return commands.getoutput("dmesg | grep CPU:") # displays cpu info
def date():
    return os.popen('date').read() # displays the date
def uptime():
    #return os.popen('uptime').read() # displays current uptime
    return commands.getoutput("uptime | awk -F', load averages:' '{ print $1 }'") # returns load averages, eg: 0.00, 0.00, 0.00
def loadavg():
    return commands.getoutput("uptime | awk -F'load averages:' '{ print $2 }'")
# returns load averages, eg; 0.00, 0.00, 0.00


##  Process Information
##

def top():
    return os.popen('top').read() # displays 'top' running processes


top_info = {
        'queryset': Top.objects.all(),
        'template_object_name': 'top_list.html',
        'extra_context': {
            'top': top,
            }
        }


freenas_info = {
        'queryset': Freenas.objects.all(),
        'template_object_name': 'freenas_list.html',
        'extra_context': {
            'hostname': hostname,
#            'freenas_version': freenas_version,
            'date': date,
            'uname1': uname1,
            'uname2': uname2,
            'platform': platform,
            'uptime': uptime,
            'loadavg': loadavg,
            }
        }
def diskwizard_wrapper(request, *args, **kwargs):
    wiz = DiskWizard([DiskAdvancedForm])
    return wiz(request, *args, **kwargs)
def volumewizard_wrapper(request, *args, **kwargs):
    wiz = VolumeWizard([VolumeTypeForm, SingleDiskForm, zpoolForm])
    return wiz(request, *args, **kwargs)

"""disk_dict = {
        'queryset': Disk.objects.(),
        }
"""

urlpatterns = patterns('',
    (r'^admin/(.*)$', admin.site.root), 
    (r'^media/(?P<path>.*)', 'django.views.static.serve', {'document_root': '/usr/local/www/freenasUI/media'}),
    (r'^freenas/media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': '/usr/local/www/freenasUI/media'}),
    (r'^/*$', list_detail.object_list, freenas_info),
    (r'^freenas/login/*$', 'django.contrib.auth.views.login', {'template_name': 'registration/login.html'}),
    ('^freenas/logout/$','django.contrib.auth.views.logout', {'template_name': 'registration/logout.html'}, 'auth_logout'),
    ('^freenas/system/general/setup/$', systemGeneralSetupView),
    ('^freenas/system/general/password/$', systemGeneralPasswordView),
    ('^freenas/system/advanced/$', systemAdvancedView),
    ('^freenas/system/advanced/email/$', systemAdvancedEmailView),
    ('^freenas/system/advanced/proxy/$', systemAdvancedProxyView),
    ('^freenas/system/advanced/swap/$', systemAdvancedSwapView),
    ('^freenas/system/advanced/commandscripts/add', CommandScriptsView),
    ('^freenas/system/advanced/commandscripts/$', systemAdvancedCommandScriptsView),
    ('^freenas/system/advanced/cronjobs/$', systemAdvancedCronView),
    ('^freenas/system/advanced/cronjobs/add/$', cronjobView),
    ('^freenas/system/advanced/rcconf/$', rcconfView),
    ('^freenas/system/advanced/rcconf/edit/$', systemAdvancedRCconfView),
    ('^freenas/system/advanced/sysctlconf/$', systemAdvancedSYSCTLconfView),
    ('^freenas/system/advanced/sysctlconf/add/$', sysctlMIBView),
    ('^freenas/network/interfaces/$', networkInterfaceMGMTView),
    ('^freenas/network/vlan/add/$', networkVLANView),
    ('^freenas/network/vlan/$', networkInterfaceMGMTvlanView),
    ('^freenas/network/lagg/add/$', networkLAGGView),
    ('^freenas/network/lagg/$', networkInterfaceMGMTlaggView),
    ('^freenas/network/hosts/$', networkHostsView),
    ('^freenas/network/staticroutes/$', networkStaticRoutesView),
    ('^freenas/network/staticroutes/add/$', StaticRoutesView),
    (r'^freenas/disk/wizard/$', 
        'django.views.generic.simple.direct_to_template', 
        {'template': 'freenas/disks/wizard.html'}),
    (r'^freenas/disk/wizard/add_disk/$', diskwizard_wrapper),
    (r'^freenas/disk/wizard/create_volume/$', volumewizard_wrapper),
    ('^freenas/system/general/setup/$', systemGeneralSetupView),
    ('^freenas/disk/management/$', DiskManagerView),
    ('^freenas/disk/management/groups/$', DiskGroupView),
    (r'^freenas/disk/management/added/$', 
        'django.views.generic.simple.direct_to_template', 
        {'template': 'freenas/disks/added.html'}),
    ('^freenas/disk/management/disks/$', disk_list),
    (r'^freenas/disks/management/disk/delete/(?P<object_id>\d)/$',
        'django.views.generic.create_update.delete_object',
        dict(model = Disk, post_delete_redirect = 'freenas/disk/management/disks/'),),
    (r'^freenas/disk/management/disks/(?P<diskid>\d)$', disk_detail),
    (r'^freenas/disk/management/volumes/(?P<volumeid>\d)$', volume_detail),
    ('^freenas/services/cifs/$', servicesCIFSView),
    ('^freenas/services/cifs/shares/add/$', shareCIFSView),
    ('^freenas/services/cifs/shares/$', servicesCIFSshareView),
    ('^freenas/services/ftp/$', servicesFTPView),
    ('^freenas/services/tftp/$', servicesTFTPView),
    ('^freenas/services/ssh/$', servicesSSHView),
    ('^freenas/services/nfs/$', servicesNFSView),
    ('^freenas/services/nfs/shares/add/$', shareNFSView),
    ('^freenas/services/nfs/shares/$', servicesNFSshareView),
    ('^freenas/services/afp/$', servicesAFPView),
    ('^freenas/services/afp/shares/add/$', shareAFPView),
    ('^freenas/services/afp/shares/$', servicesAFPshareView),
    ('^freenas/services/rsync/clientjobs/$', clientrsyncjobView),
    ('^freenas/services/rsync/localjobs/$', localrsyncjobView),
    ('^freenas/services/rsync/$', servicesRSYNCView),
    ('^freenas/services/unison/$', servicesUnisonView),
    ('^freenas/services/iscsi/$', servicesiSCSITargetView),
    ('^freenas/services/dyndns/$', servicesDynamicDNSView),
    ('^freenas/services/snmp/$', servicesSNMPView),
    ('^freenas/services/ups/$', servicesUPSView),
    ('^freenas/services/webserver/$', servicesWebserverView),
    ('^freenas/services/bittorrent/$', servicesBitTorrentView),
    (r'^freenas/status/processes/*$', list_detail.object_list, top_info),
    )
