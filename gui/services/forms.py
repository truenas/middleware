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
from django.core.exceptions import ObjectDoesNotExist
from freenasUI.services.models import *                         
from freenasUI.storage.models import *
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 
from freenasUI.common.forms import ModelForm
from freenasUI.common.forms import Form
from django import forms
from dojango.forms import fields, widgets

""" Services """

class servicesForm(ModelForm):
    class Meta:
        model = services

class CIFSForm(ModelForm):
    class Meta:
        model = CIFS
    def save(self):
        super(CIFSForm, self).save()
        notifier().reload("cifs")

class AFPForm(ModelForm):
    class Meta:
        model = AFP
    def save(self):
        super(AFPForm, self).save()
        notifier().restart("afp")

class NFSForm(ModelForm):
    class Meta:
        model = NFS
    def save(self):
        super(NFSForm, self).save()
        notifier().restart("nfs")

class FTPForm(ModelForm):
    def save(self):
        super(FTPForm, self).save()
        notifier().reload("ftp")
    class Meta:
        model = FTP 

class TFTPForm(ModelForm):
    def save(self):
        super(TFTPForm, self).save()
        notifier().reload("tftp")
    class Meta:
        model = TFTP 

class SSHForm(ModelForm):
    def save(self):
        super(SSHForm, self).save()
        notifier().reload("ssh")
    class Meta:
        model = SSH 

class iSCSITargetForm(ModelForm):
    class Meta:
        model = iSCSITarget

class DynamicDNSForm(ModelForm):
    class Meta:
        model = DynamicDNS

class SNMPForm(ModelForm):
    class Meta:
        model = SNMP

class UPSForm(ModelForm):
    class Meta:
        model = UPS

class ActiveDirectoryForm(ModelForm):
    def save(self):
        super(ActiveDirectoryForm, self).save()
        notifier().restart("activedirectory")
    class Meta:
        model = ActiveDirectory

class LDAPForm(ModelForm):
    def save(self):
        super(LDAPForm, self).save()
        notifier().restart("ldap")
    class Meta:
        model = LDAP

class iSCSITargetAuthCredentialForm(ModelForm):
    iscsi_target_auth_secret1 = forms.CharField(label="Secret", widget=forms.PasswordInput, help_text="Target side secret.")
    iscsi_target_auth_secret2 = forms.CharField(label="Secret (Confirm)", widget=forms.PasswordInput, help_text="Enter the same secret above for verification.")
    iscsi_target_auth_peersecret1 = forms.CharField(label="Initiator Secret", widget=forms.PasswordInput, help_text="Initiator side secret. (for mutual CHAP autentication)")
    iscsi_target_auth_peersecret2 = forms.CharField(label="Initiator Secret (Confirm)", widget=forms.PasswordInput, help_text="Enter the same secret above for verification.")

    def _clean_secret_common(self, secretprefix):
        secret1 = self.cleaned_data.get(("%s1" % secretprefix), "")
        secret2 = self.cleaned_data[("%s2" % secretprefix)]
        if secret1 != secret2:
            raise forms.ValidationError("Secret does not match")
        return secret2

    def clean_iscsi_target_auth_secret2(self):
        return self._clean_secret_common("iscsi_target_auth_secret")

    def clean_iscsi_target_auth_peersecret2(self):
        return self._clean_secret_common("iscsi_target_auth_peersecret")

    class Meta:
        model = iSCSITargetAuthCredential
        exclude = ('iscsi_target_auth_secret', 'iscsi_target_auth_peersecret',)

    def save(self, commit=True):
        oAuthCredential = super(iSCSITargetAuthCredentialForm, self).save(commit=False)
        oAuthCredential.iscsi_target_auth_secret = self.cleaned_data["iscsi_target_auth_secret1"]
        oAuthCredential.iscsi_target_peerauth_secret = self.cleaned_data["iscsi_target_auth_peersecret1"]
        if commit:
            oAuthCredential.save()
        return oAuthCredential

class iSCSITargetToExtentForm(ModelForm):
    class Meta:
        model = iSCSITargetToExtent
    def clean_iscsi_target_lun(self):
        try:
            obj = iSCSITargetToExtent.objects.get(iscsi_target=self.cleaned_data.get('iscsi_target'),
                                                  iscsi_target_lun=self.cleaned_data.get('iscsi_target_lun'))
            raise forms.ValidationError("LUN already exists in the same target.")
        except ObjectDoesNotExist:
            return self.cleaned_data.get('iscsi_target_lun')

class iSCSITargetGlobalConfigurationForm(ModelForm):
    class Meta:
        model = iSCSITargetGlobalConfiguration

class iSCSITargeExtentEditForm(ModelForm):
    class Meta:
        model = iSCSITargetExtent
        exclude = ('iscsi_target_extent_type', 'iscsi_target_extent_path',)

class iSCSITargetFileExtentForm(ModelForm):
    class Meta:
        model = iSCSITargetExtent
        exclude = ('iscsi_target_extent_type')
    def save(self, commit=True):
        oExtent = super(iSCSITargetFileExtentForm, self).save(commit=False)
        oExtent.iscsi_target_extent_type = 'File'
        if commit:
            oExtent.save()
        return oExtent

attrs_dict = { 'class': 'required' }
class iSCSITargetDeviceExtentForm(ModelForm):
    iscsi_extent_disk = forms.ChoiceField(choices=(), widget=forms.Select(attrs=attrs_dict), label = 'Disk device')
    def __init__(self, *args, **kwargs):
        super(iSCSITargetDeviceExtentForm, self).__init__(*args, **kwargs)
        self.fields['iscsi_extent_disk'].choices = self._populate_disk_choices()
        self.fields['iscsi_extent_disk'].choices.sort()
    # TODO: This is largely the same with disk wizard.
    def _populate_disk_choices(self):
        from os import popen
        import re
    
        diskchoices = dict()
    
        # Grab disk list
        # NOTE: This approach may fail if device nodes are not accessible.
        pipe = popen("/usr/sbin/diskinfo ` /sbin/sysctl -n kern.disks` | /usr/bin/cut -f1,3")
        diskinfo = pipe.read().strip().split('\n')
        for disk in diskinfo:
            devname, capacity = disk.split('\t')
            capacity = int(capacity)
            if capacity >= 1099511627776:
                    capacity = "%.1f TiB" % (capacity / 1099511627776.0)
            elif capacity >= 1073741824:
                    capacity = "%.1f GiB" % (capacity / 1073741824.0)
            elif capacity >= 1048576:
                    capacity = "%.1f MiB" % (capacity / 1048576.0)
            else:
                    capacity = "%d Bytes" % (capacity)
            diskchoices[devname] = "%s (%s)" % (devname, capacity)
        # Exclude the root device
        rootdev = popen("""glabel status | grep `mount | awk '$3 == "/" {print $1}' | sed -e 's/\/dev\///'` | awk '{print $3}'""").read().strip()
        rootdev_base = re.search('[a-z/]*[0-9]*', rootdev)
        if rootdev_base != None:
            try:
                del diskchoices[rootdev_base.group(0)]
            except:
                pass
        # Exclude what's already added
        for devname in [ x['disk_disks'] for x in Disk.objects.all().values('disk_disks')]:
            try:
                del diskchoices[devname]
            except:
                pass
        return diskchoices.items()
    class Meta:
        model = iSCSITargetExtent
        exclude = ('iscsi_target_extent_type', 'iscsi_target_extent_path', 'iscsi_target_extent_filesize')
    def save(self, commit=True):
        oExtent = super(iSCSITargetDeviceExtentForm, self).save(commit=False)
        oExtent.iscsi_target_extent_type = 'Disk'
        oExtent.iscsi_target_extent_filesize = 0
        oExtent.iscsi_target_extent_path = '/dev/' + self.cleaned_data["iscsi_extent_disk"]
        if commit:
            oExtent.save()
            # Construct a corresponding volume.
            volume_name = 'iscsi:' + self.cleaned_data["iscsi_extent_disk"]
            volume_fstype = 'iscsi'

            volume = Volume(vol_name = volume_name, vol_fstype = volume_fstype)
            volume.save()

            disk_list = [ self.cleaned_data["iscsi_extent_disk"] ]

            mp = MountPoint(mp_volume=volume, mp_path=volume_name, mp_options='noauto')
            mp.save()

            grp = DiskGroup(group_name= volume_name, group_type = 'raw', group_volume = volume)
            grp.save()

            diskobj = Disk(disk_name = self.cleaned_data["iscsi_extent_disk"],
                           disk_disks = self.cleaned_data["iscsi_extent_disk"],
                           disk_description = 'iSCSI exported disk',
                           disk_group = grp)
            diskobj.save()
        return oExtent

class iSCSITargetPortalForm(ModelForm):
    class Meta:
        model = iSCSITargetPortal

class iSCSITargetAuthorizedInitiatorForm(ModelForm):
    class Meta:
        model = iSCSITargetAuthorizedInitiator

class iSCSITargetForm(ModelForm):
    class Meta:
        model = iSCSITarget
