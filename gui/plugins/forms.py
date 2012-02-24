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
import os

from django.forms import FileField
from django.utils.translation import ugettext_lazy as _, ugettext as __
from django.shortcuts import render_to_response

from . import models
from dojango import forms
from freenasUI.common.forms import ModelForm, Form
from freenasUI.freeadmin.views import JsonResponse
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import MountPoint
from freenasUI.system.forms import FileWizard
from freenasUI.account.forms import FilteredSelectField
from freenasUI import services, storage, network, choices


class PBIFileWizard(FileWizard):
    def done(self, request, form_list):
        retval = getattr(self, 'retval', None)
        events = []
        if not retval:
            events.append('restartHttpd()')
        return JsonResponse(
            error=bool(retval),
            message=retval if retval else __("PBI successfully installed."),
            enclosed=not request.is_ajax(),
            events=events,
            )

class PluginsForm(ModelForm):
    class Meta:
        model = models.Plugins
        exclude = ('plugin_pbiname', 'plugin_arch', 'plugin_version', 'plugin_path')

    def __init__(self, *args, **kwargs):
        super(PluginsForm, self).__init__(*args, **kwargs)
        self.instance._original_plugin_enabled = self.instance.plugin_enabled

    def save(self):
        super(PluginsForm, self).save()
        notifier()._restart_plugins(self.instance.plugin_name)


class PBITemporaryLocationForm(Form):
    mountpoint = forms.ChoiceField(label=_("Place to temporarily place PBI file"), help_text = _("The system will use this place to temporarily store the PBI file before it's installed."), choices=(), widget=forms.Select(attrs={ 'class': 'required' }),)
    def __init__(self, *args, **kwargs):
        super(PBITemporaryLocationForm, self).__init__(*args, **kwargs)
        mp = services.models.Plugins.objects.order_by("-id")
        if mp and notifier().plugins_jail_configured():
            mp = mp[0]
            self.fields['mountpoint'].choices = [(mp.plugins_path, mp.plugins_path)]
        else:
            self.fields['mountpoint'].choices = [(x.mp_path, x.mp_path) for x in MountPoint.objects.exclude(mp_volume__vol_fstype='iscsi')]
    def done(self, *args, **kwargs):
        notifier().change_upload_location(self.cleaned_data["mountpoint"].__str__())


class PBIUploadForm(Form):
    pbifile = FileField(label=_("PBI file to be installed"), required=True)
    sha256 = forms.CharField(label=_("SHA256 sum for the PBI file"), required=True)
    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/firmware/pbifile.pbi'
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
    def done(self, *args, **kwargs):
        notifier().install_pbi()

class JailPBIUploadForm(Form):

#
#    Yuck. This is a form-i-fied version of the services Plugin model.
#    FileWizard does not render the form correctly when using a ModelForm
#    based class, so we handle it this way... for now.
#
    jail_path = forms.ChoiceField(
            label=_("Plugins jail path"),
            choices=(),
            widget=forms.Select(attrs={ 'class': 'required' }),
            )
    jail_name = forms.CharField(
            label= _("Jail name"),
            required=True
            )
    jail_ip = forms.ChoiceField(
            label=_("Jail IP address"),
            choices=(),
            required=True
            )
    plugins_path = forms.ChoiceField(
            label=_("Plugins Path"),
            choices=(),
            widget=forms.Select(attrs={ 'class': 'required' }),
            )
    pbifile = FileField(
            label=_("Plugins Jail PBI"),
            required=True
            )
    sha256 = forms.CharField(
            label=_("SHA256 sum for the PBI file"),
            required=True
             )

    def __init__(self, *args, **kwargs):
        from freenasUI.network import models

        super(JailPBIUploadForm, self).__init__(*args, **kwargs)

        path_list = []
        mp_list = storage.models.MountPoint.objects.exclude(mp_volume__vol_fstype__exact='iscsi').select_related().all()
        for m in mp_list:
            path_list.append(m.mp_path)

            datasets = m.mp_volume.get_datasets()
            if datasets:
                for name, dataset in datasets.items():
                    path_list.append(dataset.mountpoint)

        nics = choices.NICChoices(with_alias=True, exclude_configured=False)
        ifaces = models.Interfaces.objects.filter(int_interface__in=[n[0] for n in nics])
        aliases = models.Alias.objects.filter(alias_interface__in=[i.id for i in ifaces])

        self.fields['jail_path'].choices = [(path, path) for path in path_list]
        self.fields['jail_ip'].choices = [(a.alias_v4address, a.alias_v4address) for a in aliases]
        self.fields['plugins_path'].choices = [(path, path) for path in path_list]

    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/firmware/pbifile.pbi'
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

    def done(self, *args, **kwargs):
        from freenasUI.network import models

        cleaned_data = self.cleaned_data

        jail_ip = self.cleaned_data['jail_ip']
        alias = models.Alias.objects.filter(alias_v4address=jail_ip)[0]

        # Create a plugins service entry
        pj = services.models.Plugins()
        pj.jail_path = cleaned_data.get('jail_path')
        pj.jail_name = cleaned_data.get('jail_name')
        pj.jail_ip = alias
        pj.plugins_path = cleaned_data.get('plugins_path')

        # Install the jail PBI
        if notifier().install_jail_pbi(pj.jail_path, pj.jail_name, pj.plugins_path):
            pj.save()
