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

from django.forms import ModelForm                             
from django.shortcuts import render_to_response                
from freenasUI.freenas.ext_formwizard import FormWizard         
from freenasUI.freenas.models import *                         
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 
from dojango.forms.models import ModelForm as ModelForm
from dojango.forms import fields, widgets 
from dojango.forms.fields import BooleanField 

class systemGeneralSetupForm(ModelForm):
    class Meta:
        model = systemGeneralSetup
    def save(self):
        super(systemGeneralSetupForm, self).save()
        notifier().reload("general")

class systemGeneralPasswordForm(ModelForm):
    class Meta:
        model = systemGeneralPassword

class systemAdvancedForm(ModelForm):
    class Meta:
        model = systemAdvanced

class systemAdvancedEmailForm(ModelForm):
    class Meta:
        model = systemAdvancedEmail

class systemAdvancedProxyForm(ModelForm):
    class Meta:
        model = systemAdvancedProxy

class systemAdvancedSwapForm(ModelForm):
    class Meta:
        model = systemAdvancedSwap

class systemAdvancedCommandScriptsForm(ModelForm):
    class Meta:
        model = systemAdvancedCommandScripts

class CommandScriptsForm(ModelForm):
    class Meta:
        model = CommandScripts

class cronjobForm(ModelForm):
    class Meta:
        model = cronjob

class systemAdvancedCronForm(ModelForm):
    class Meta:
        model = systemAdvancedCron

class systemAdvancedRCconfForm(ModelForm):
    class Meta:
        model = systemAdvancedRCconf

class rcconfForm(ModelForm):
    class Meta:
        model = rcconf

class systemAdvancedSYSCTLconfForm(ModelForm):
    class Meta:
        model = systemAdvancedSYSCTLconf

class sysctlMIBForm(ModelForm):
    class Meta:
        model = sysctlMIB

class networkInterfaceMGMTForm(ModelForm):
    class Meta:
        model = networkInterfaceMGMT 
    def save(self):
        # TODO: new IP address should be added in a side-by-side manner
	# or the interface wouldn't appear once IP was changed.
        super(networkInterfaceMGMTForm, self).save()
        notifier().start("network")

class networkVLANForm(ModelForm):
    class Meta:
        model = networkVLAN 
class networkLAGGForm(ModelForm):
    class Meta:
        model = networkLAGG
class networkStaticRouteForm(ModelForm):
    class Meta:
        model = networkStaticRoute
    def save(self):
        super(networkStaticRouteForm, self).save()
        notifier().start("routing")

class DiskForm(ModelForm):
    class Meta:
        model = Disk

class DiskGroupForm(ModelForm):
    class Meta:
        model = DiskGroup

class zpoolForm(ModelForm):
    class Meta:
        model = zpool 

class VolumeForm(ModelForm):
    class Meta:
        model = Volume
    def save(self):
        vinstance = super(VolumeForm, self).save()
        # Create the inherited mountpoint
        mp = MountPoint(volumeid=vinstance, mountpoint='/mnt/' + self.cleaned_data['vol_name'], mountoptions='rw')
        mp.save()
        notifier().create("disk")

""" Shares """
class MountPointForm(ModelForm):
    class Meta:
        model = MountPoint

class WindowsShareForm(ModelForm):
    class Meta:
        model = WindowsShare 
    def save(self):
        super(WindowsShareForm, self).save()
        notifier().reload("smbd")

class AppleShareForm(ModelForm):
    class Meta:
        model = AppleShare 

class UnixShareForm(ModelForm):
    class Meta:
        model = UnixShare 
    def save(self):
        super(UnixShareForm, self).save()
        notifier().reload("nfsd")

""" Services """

class servicesCIFSForm(ModelForm):
    class Meta:
        model = servicesCIFS
    def save(self):
        super(servicesCIFSForm, self).save()
        notifier().reload("smbd")

class servicesAFPForm(ModelForm):
    class Meta:
        model = servicesAFP

class servicesNFSForm(ModelForm):
    class Meta:
        model = servicesNFS
    def save(self):
        super(servicesNFSForm, self).save()
        notifier().restart("nfsd")

class servicesFTPForm(ModelForm):
    def save(self):
        super(servicesFTPForm, self).save()
        notifier().reload("ftp")
    class Meta:
        model = servicesFTP 

class servicesTFTPForm(ModelForm):
    def save(self):
        super(servicesTFTPForm, self).save()
        notifier().reload("tftp")
    class Meta:
        model = servicesTFTP 

class servicesSSHForm(ModelForm):
    def save(self):
        super(servicesSSHForm, self).save()
        notifier().reload("ssh")
    class Meta:
        model = servicesSSH 

class clientrsyncjobForm(ModelForm):
    class Meta:
        model = clientrsyncjob

class localrsyncjobForm(ModelForm):
    class Meta:
        model = localrsyncjob

class servicesRSYNCForm(ModelForm):
    class Meta:
        model = servicesRSYNC

class servicesUnisonForm(ModelForm):
    class Meta:
        model = servicesUnison

class servicesiSCSITargetForm(ModelForm):
    class Meta:
        model = servicesiSCSITarget

class servicesDynamicDNSForm(ModelForm):
    class Meta:
        model = servicesDynamicDNS

class servicesSNMPForm(ModelForm):
    class Meta:
        model = servicesSNMP

class servicesUPSForm(ModelForm):
    class Meta:
        model = servicesUPS

class servicesWebserverForm(ModelForm):
    class Meta:
        model = servicesWebserver

class servicesBitTorrentForm(ModelForm):
    class Meta:
        model = servicesBitTorrent


""" Access """

class accessActiveDirectoryForm(ModelForm):
    class Meta:
        model = accessActiveDirectory

class accessLDAPForm(ModelForm):
    class Meta:
        model = accessLDAP

