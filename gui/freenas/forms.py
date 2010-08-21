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

#from dojango.forms import forms                                
from django.forms import ModelForm                             
from django.shortcuts import render_to_response                
#from django.contrib.formtools.wizard import FormWizard         
## Using Extended Form Wizard instead: 
## http://djangosnippets.org/snippets/1454/
from freenasUI.freenas.ext_formwizard import FormWizard         
from freenasUI.freenas.models import *                         
from freenasUI.freenas.models import TOGGLE_CHOICES
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.forms.widgets import RadioFieldRenderer
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 


class RadioFieldRendererEx(RadioFieldRenderer): # alternate renderer for horiz. radios
    outer = u"<span>%s</span>"
    inner= u"%s"
    def render(self):
         return mark_safe(self.outer % u'\n'.join ([ self.inner % w for w in self ]))

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
        widgets = {
                'consolemenu': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'serialconsole': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'consolescreensaver': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'firmwarevc': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'systembeep': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'tuning': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'powerdaemon': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'zeroconfbonjour': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
        

class systemAdvancedEmailForm(ModelForm):
    class Meta:
        model = systemAdvancedEmail
        widgets = {
                'smtp': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
class systemAdvancedProxyForm(ModelForm):
    class Meta:
        model = systemAdvancedProxy
        widgets = {
                'httpproxy': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'httpproxyauth': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'ftpproxy': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'ftpproxyauth': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
class systemAdvancedSwapForm(ModelForm):
    class Meta:
        model = systemAdvancedSwap
        widgets = {
                'swapmemory': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
class systemAdvancedCommandScriptsForm(ModelForm):
    class Meta:
        model = systemAdvancedCommandScripts
class CommandScriptsForm(ModelForm):
    class Meta:
        model = CommandScripts
class cronjobForm(ModelForm):
    class Meta:
        model = cronjob
        widgets = {
                'togglecron': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'ToggleMinutes': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Minutes1': forms.SelectMultiple(),
                'Minutes2': forms.SelectMultiple(),
                'Minutes3': forms.SelectMultiple(),
                'Minutes4': forms.SelectMultiple(),
                'ToggleHours': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Hours1': forms.SelectMultiple(),
                'Hours2': forms.SelectMultiple(),
                'ToggleDays': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Days1': forms.SelectMultiple(),
                'Days2': forms.SelectMultiple(),
                'Days3': forms.SelectMultiple(),
                'ToggleMonths': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Months': forms.SelectMultiple(),
                'ToggleWeekdays': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Weekdays': forms.SelectMultiple(),
                }
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
class networkInterfaceMGMTvlanForm(ModelForm):
    class Meta:
        model = networkInterfaceMGMTvlan
class networkLAGGForm(ModelForm):
    class Meta:
        model = networkLAGG
class networkInterfaceMGMTlaggForm(ModelForm):
    class Meta:
        model = networkInterfaceMGMTlagg
class networkHostsForm(ModelForm):
    class Meta:
        model = networkHosts
class StaticRoutesForm(ModelForm):
    class Meta:
        model = StaticRoutes
class networkStaticRoutesForm(ModelForm):
    class Meta:
        model = networkStaticRoutes
"""
Django's FormWizard uses multiple Django Forms to create a multi-step wizard
"""
class DiskWizard(FormWizard):
    def prefix_for_step(self, step):
        # Given the step, returns a form prefix to use. 
        # By default, this simply uses the step itself
        return str("step_") + str(step)
    def get_template(self, step):
        return 'forms/disk_wizard_%s.html' % step
    def done(self, request, form_list): # saves form to db
        for form in form_list: 
            form.save() 
            #form.save([force_insert=True]) 
      #  return render_to_response('forms/disk_wizard.html', {
      #      'form_data': [form.cleaned_data for form in form_list],
      #      })
        return HttpResponseRedirect('/freenas/disk/management/disks/') # Redirect after POST

class DiskForm(ModelForm):
    class Meta:
        model = Disk

class DiskAdvancedForm(ModelForm):
    class Meta:
        model = DiskAdvanced

class DiskGroupForm(ModelForm):
    class Meta:
        model = DiskGroup
        widgets = {
                'group': forms.SelectMultiple(),
                }

class SingleDiskForm(ModelForm):
    class Meta:
        model = SingleDisk

class zpoolForm(ModelForm):
    class Meta:
        model = zpool 

class VolumeWizard(FormWizard):
    def process_step(self, request, form, step):
        # Step 0 asks which volume "type" (filesystem)
        # and drops the user to the correct form
        if step==0:
            if form.cleaned_data['type']=='zfs':
                self.form_list.remove(SingleDiskForm)
            else:
                self.form_list.remove(zpoolForm)
    def prefix_for_step(self, step):
        # Given the step, returns a form prefix to use. 
        # By default, this simply uses the step itself
        return str("step_") + str(step)
    def get_template(self, step):
        return 'forms/volume_wizard_%s.html' % step
    def done(self, request, form_list): # saves form to db
        for form in form_list: 
            form.save() 
            #form.save([force_insert=True]) 
      #  return render_to_response('forms/disk_wizard.html', {
      #      'form_data': [form.cleaned_data for form in form_list],
      #      })
        return HttpResponseRedirect('/freenas/disk/management/added/')

class VolumeForm(ModelForm):
    class Meta:
        model = Volume
        widgets = {
                'disks': forms.SelectMultiple(),
                }
    def save(self):
        super(VolumeForm, self).save()
        notifier().create("disk")

class VolumeTypeForm(ModelForm):
    class Meta:
        model = Volume


class servicesCIFSForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(servicesCIFSForm, self).__init__(*args, **kwargs)
        self.fields['togglecifs'].widget.attrs['class'] = 'cifs_test_class'
        self.fields['localmaster'].widget.attrs['class'] = 'cifs_test_class'
        self.fields['timeserver'].widget.attrs['class'] = 'cifs_test_class'

    #error_css_class = 'form_error'
    #required_css_class = 'form_required'

    class Meta:
        model = servicesCIFS
        widgets = {
                'togglecifs': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'localmaster': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'timeserver': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'largerw': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'sendfile': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'easupport': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'dosattr': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'nullpw': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
    def save(self):
        super(servicesCIFSForm, self).save()
        notifier().reload("smbd")

class shareCIFSForm(ModelForm):
    class Meta:
        model = shareCIFS 
        widgets = {
                'ro': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'browseable': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'inheritperms': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'recyclebin': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'showhiddenfiles': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
    def save(self):
        super(shareCIFSForm, self).save()
        notifier().reload("smbd")

class servicesCIFSshareForm(ModelForm):
    class Meta:
        model = servicesCIFSshare

class servicesFTPForm(ModelForm):
    def save(self):
        super(servicesFTPForm, self).save()
        notifier().reload("ftp")
    class Meta:
        model = servicesFTP 
        widgets = {
                'toggleFTP': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'rootlogin': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'onlyanonymous': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'onlylocal': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'fxp': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'resume': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'defaultroot': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'ident': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'reversedns': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'ssltls': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesTFTPForm(ModelForm):
    def save(self):
        super(servicesTFTPForm, self).save()
        notifier().reload("tftp")
    class Meta:
        model = servicesTFTP 
        widgets = {
                'toggleTFTP': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'newfiles': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesSSHForm(ModelForm):
    def save(self):
        super(servicesSSHForm, self).save()
        notifier().reload("ssh")
    class Meta:
        model = servicesSSH 
        widgets = {
                'toggleSSH': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'rootlogin': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'passwordauth': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'tcpfwd': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'compression': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesNFSForm(ModelForm):
    class Meta:
        model = servicesNFS
        widgets = {
                'toggleNFS': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class shareNFSForm(ModelForm):
    class Meta:
        model = shareNFS
        widgets = {
                'allroot': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'alldirs': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'readonly': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'quiet': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
    def save(self):
        super(shareNFSForm, self).save()
        notifier().reload("nfsd")

class servicesNFSshareForm(ModelForm):
    class Meta:
        model = servicesNFSshare

class servicesAFPForm(ModelForm):
    class Meta:
        model = servicesAFP
        widgets = {
                'toggleAFP': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'guest': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'local': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'ddp': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class shareAFPForm(ModelForm):
    class Meta:
        model = shareAFP
        widgets = {
                'cachecnid': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'crlf': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'mswindows': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'noadouble': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'nodev': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'nofileid': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'nohex': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'prodos': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'nostat': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'upriv': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'diskdiscovery': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'discoverymode': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesAFPshareForm(ModelForm):
    class Meta:
        model = servicesAFPshare

class clientrsyncjobForm(ModelForm):
    class Meta:
        model = clientrsyncjob
        widgets = {
                'ToggleMinutes': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Minutes1': forms.SelectMultiple(),
                'Minutes2': forms.SelectMultiple(),
                'Minutes3': forms.SelectMultiple(),
                'Minutes4': forms.SelectMultiple(),
                'ToggleHours': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Hours1': forms.SelectMultiple(),
                'Hours2': forms.SelectMultiple(),
                'ToggleDays': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Days1': forms.SelectMultiple(),
                'Days2': forms.SelectMultiple(),
                'Days3': forms.SelectMultiple(),
                'ToggleMonths': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Months': forms.SelectMultiple(),
                'ToggleWeekdays': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Weekdays': forms.SelectMultiple(),
                'recursive': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'times': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'compress': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'archive': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'delete': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'quiet': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'preserveperms': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'extattr': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class localrsyncjobForm(ModelForm):
    class Meta:
        model = localrsyncjob
        widgets = {
                'ToggleMinutes': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Minutes1': forms.SelectMultiple(),
                'Minutes2': forms.SelectMultiple(),
                'Minutes3': forms.SelectMultiple(),
                'Minutes4': forms.SelectMultiple(),
                'ToggleHours': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Hours1': forms.SelectMultiple(),
                'Hours2': forms.SelectMultiple(),
                'ToggleDays': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Days1': forms.SelectMultiple(),
                'Days2': forms.SelectMultiple(),
                'Days3': forms.SelectMultiple(),
                'ToggleMonths': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Months': forms.SelectMultiple(),
                'ToggleWeekdays': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'Weekdays': forms.SelectMultiple(),
                'recursive': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'times': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'compress': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'archive': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'delete': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'quiet': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'preserveperms': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'extattr': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesRSYNCForm(ModelForm):
    class Meta:
        model = servicesRSYNC
        widgets = {
                'togglersync': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesUnisonForm(ModelForm):
    class Meta:
        model = servicesUnison
        widgets = {
                'toggleUnison': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesiSCSITargetForm(ModelForm):
    class Meta:
        model = servicesiSCSITarget
        widgets = {
                'toggleiSCSITarget': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'toggleluc': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesDynamicDNSForm(ModelForm):
    class Meta:
        model = servicesDynamicDNS
        widgets = {
                'toggleDynamicDNS': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'wildcard': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
class servicesSNMPForm(ModelForm):
    class Meta:
        model = servicesSNMP
        widgets = {
                'toggleSNMP': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'traps': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
class servicesUPSForm(ModelForm):
    class Meta:
        model = servicesUPS
        widgets = {
                'toggleUPS': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'rmonitor': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'emailnotify': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

class servicesWebserverForm(ModelForm):
    class Meta:
        model = servicesWebserver
        widgets = {
                'toggleWebserver': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'auth': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'dirlisting': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }
class servicesBitTorrentForm(ModelForm):
    class Meta:
        model = servicesBitTorrent
        widgets = {
                'toggleBitTorrent': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'portfwd': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'pex': forms.RadioSelect(renderer=RadioFieldRendererEx),
                'disthash': forms.RadioSelect(renderer=RadioFieldRendererEx),
                }

# The following displays the Setup Wizard  
class Merlin(FormWizard):
    def prefix_for_step(self, step):
        # Given the step, returns a form prefix to use. 
        # By default, this simply uses the step itself
        return str("step_") + str(step)
    def done(self, request, form_list): # saves form to db
        for form in form_list: 
            form.save() 
            #form.save([force_insert=True]) 
        return render_to_response('forms/wizard.html', {
            'form_data': [form.cleaned_data for form in form_list],
            })

