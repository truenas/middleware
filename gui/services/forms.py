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
from freenasUI.services.models import *                         
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 
from dojango.forms.models import ModelForm as ModelForm
from dojango.forms import fields, widgets
from dojango import forms

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

class rsyncjobForm(ModelForm):
    class Meta:
        model = rsyncjob

class UnisonForm(ModelForm):
    class Meta:
        model = Unison

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

class WebserverForm(ModelForm):
    class Meta:
        model = Webserver

class BitTorrentForm(ModelForm):
    class Meta:
        model = BitTorrent

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

class iSCSITargetGlobalConfigurationForm(ModelForm):
    class Meta:
        model = iSCSITargetGlobalConfiguration

class iSCSITargetExtentForm(ModelForm):
    class Meta:
        model = iSCSITargetExtent

class iSCSITargetPortalForm(ModelForm):
    class Meta:
        model = iSCSITargetPortal

class iSCSITargetAuthorizedInitiatorForm(ModelForm):
    class Meta:
        model = iSCSITargetAuthorizedInitiator

class iSCSITargetForm(ModelForm):
    class Meta:
        model = iSCSITarget
