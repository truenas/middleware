#+
# Copyright 2011 iXsystems, Inc.
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
#####################################################################

from django.forms import FileField
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.common.forms import ModelForm, Form
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import MountPoint
from plugins import models


class PluginsForm(ModelForm):
    class Meta:
        model = models.Plugins
    def __init__(self, *args, **kwargs):
        super(PluginsForm, self).__init__(*args, **kwargs)
        self.instance._original_plugin_enabled = self.instance.plugin_enabled
    def save(self):
        super(PluginsForm, self).save()
        if self.instance._original_plugin_enabled != self.instance.plugin_enabled:
            notifier()._restart_plugins(self.instance.plugin_name)


class PBITemporaryLocationForm(Form):
    mountpoint = forms.ChoiceField(label=_("Place to temporarily place PBI file"), help_text = _("The system will use this place to temporarily store the PBI file before it's installed."), choices=(), widget=forms.Select(attrs={ 'class': 'required' }),)
    def __init__(self, *args, **kwargs):
        from freenasUI import services
        super(PBITemporaryLocationForm, self).__init__(*args, **kwargs)
        mp = services.models.Plugins.objects.order_by("-id")
        if mp:
            mp = mp[0]
            self.fields['mountpoint'].choices = [(mp.plugins_path, mp.plugins_path)]
        else:
            self.fields['mountpoint'].choices = [(x.mp_path, x.mp_path) for x in MountPoint.objects.exclude(mp_volume__vol_fstype='iscsi')]
    def done(self):
        notifier().change_upload_location(self.cleaned_data["mountpoint"].__str__(), pbi=True)


class PBIUploadForm(Form):
    pbifile = FileField(label=_("PBI fileto be installed"), required=True)
    sha256 = forms.CharField(label=_("SHA256 sum for the PBI file"), required=True)
    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/pbi/pbifile.pbi'
        if cleaned_data.get('pbifile'):
            with open(filename, 'wb+') as sp:
                for c in cleaned_data['pbifile'].chunks():
                    sp.write(c)
            if 'sha256' in cleaned_data:
                checksum = notifier().checksum(filename)
                if checksum != str(cleaned_data['sha256']):
                    msg = _(u"Invalid checksum")
                    self._errors["pbifile"] = self.error_class([msg])
                    del cleaned_data["pbifile"]
        else:
            self._errors["pbifile"] = self.error_class([_("This field is required.")])
        return cleaned_data
    def done(self):
        return notifier().install_pbi()

class JailPBIUploadForm(Form):
    pbifile = FileField(label=_("Plugins Jail PBI"), required=True)
    sha256 = forms.CharField(label=_("SHA256 sum for the PBI file"), required=True)
    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/pbi/pbifile.pbi'
        if cleaned_data.get('pbifile'):
            with open(filename, 'wb+') as sp:
                for c in cleaned_data['pbifile'].chunks():
                    sp.write(c)
            if 'sha256' in cleaned_data:
                checksum = notifier().checksum(filename)
                if checksum != str(cleaned_data['sha256']):
                    msg = _(u"Invalid checksum")
                    self._errors["pbifile"] = self.error_class([msg])
                    del cleaned_data["pbifile"]
        else:
            self._errors["pbifile"] = self.error_class([_("This field is required.")])
        return cleaned_data
    def done(self):
        #return notifier().install_pbi()
        pass
