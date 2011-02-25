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

from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render_to_response                
from freenasUI.system.models import *                         
from freenasUI.middleware.notifier import notifier
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode 
from freenasUI.common.forms import ModelForm
from freenasUI.common.forms import Form
from dojango.forms import fields, widgets 
from dojango.forms.fields import BooleanField 
from dojango import forms
# TODO: dojango.forms.FileField seems to have some bug that mangles the interface
# so we use django.forms.FileField for this release.
import django.forms


class SettingsForm(ModelForm):
    class Meta:
        model = Settings
    def __init__(self, *args, **kwargs):
        super(SettingsForm, self).__init__( *args, **kwargs)
        self.instance._original_stg_guiprotocol = self.instance.stg_guiprotocol
    def save(self):
        if self.instance._original_stg_guiprotocol != self.instance.stg_guiprotocol:
            notifier().restart("http")
        super(SettingsForm, self).save()
        notifier().reload("timeservices")

class AdvancedForm(ModelForm):
    class Meta:
        model = Advanced

class EmailForm(ModelForm):
    em_pass1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput, required=False)
    em_pass2 = forms.CharField(label=_("Password confirmation"), widget=forms.PasswordInput,
        help_text = _("Enter the same password as above, for verification."), required=False)
    class Meta:
        model = Email
        exclude = ('em_pass',)
    def __init__(self, *args, **kwargs):
        super(EmailForm, self).__init__( *args, **kwargs)
        try:
            self.fields['em_pass1'].initial = self.instance.em_pass
            self.fields['em_pass2'].initial = self.instance.em_pass
        except:
            pass
        self.fields['em_smtp'].widget.attrs['onChange'] = 'javascript:toggleEmail(this);'
        ro = True

        if len(self.data) > 0:
            if self.data.get("em_smtp", None) == "on":
                ro = False
        else:
            if self.instance.em_smtp == True:
                ro = False
        if ro:
            self.fields['em_user'].widget.attrs['disabled'] = 'disabled'
            self.fields['em_pass1'].widget.attrs['disabled'] = 'disabled' 
            self.fields['em_pass2'].widget.attrs['disabled'] = 'disabled' 

    def clean_em_user(self):
        if self.cleaned_data['em_smtp'] == True and \
                self.cleaned_data['em_user'] == "":
            raise forms.ValidationError(_("This field is required"))
        return self.cleaned_data['em_user']

    def clean_em_pass1(self):
        if self.cleaned_data['em_smtp'] == True and \
                self.cleaned_data['em_pass1'] == "":
            raise forms.ValidationError(_("This field is required"))
        return self.cleaned_data['em_pass1']
    def clean_em_pass2(self):
        if self.cleaned_data['em_smtp'] == True and \
                self.cleaned_data.get('em_pass2', "") == "":
            raise forms.ValidationError(_("This field is required"))
        pass1 = self.cleaned_data.get("em_pass1", "")
        pass2 = self.cleaned_data.get("em_pass2", "")
        if pass1 != pass2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return pass2
    def save(self, commit=True):
        email = super(EmailForm, self).save(commit=False)
        if commit:
             email.em_pass = self.cleaned_data['em_pass2']
             email.save()
             notifier().start("ix-msmtp")
        return email

class FirmwareTemporaryLocationForm(Form):
    mountpoint = forms.ChoiceField(label="Place to temporarily place firmware file", help_text = _("The system will use this place to temporarily store the firmware file before it's being applied."),choices=(), widget=forms.Select(attrs={ 'class': 'required' }),)
    def __init__(self, *args, **kwargs):
        from freenasUI.storage.models import MountPoint
        super(FirmwareTemporaryLocationForm, self).__init__(*args, **kwargs)
        self.fields['mountpoint'].choices = [(x.mp_path, x.mp_path) for x in MountPoint.objects.all()]
    def done(self):
        notifier().change_upload_location(self.cleaned_data["mountpoint"].__str__())

class FirmwareUploadForm(Form):
    firmware = django.forms.FileField(label=_("New image to be installed"))
    sha256 = forms.CharField(label=_("SHA256 sum for the image"))
    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/firmware/firmware.xz'
        fw = open(filename, 'wb+')
        for c in self.files['firmware'].chunks():
            fw.write(c)
        fw.close()
        checksum = notifier().checksum(filename)
        retval = notifier().validate_xz(filename)
        if checksum != cleaned_data['sha256'].__str__() or retval == False:
            msg = u"Invalid firmware or checksum"
            self._errors["firmware"] = self.error_class([msg])
            del cleaned_data["firmware"]
        return cleaned_data
    def done(self):
        notifier().update_firmware('/var/tmp/firmware/firmware.xz')

