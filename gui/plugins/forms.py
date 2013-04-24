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
import logging
import os
import shutil

from django.forms import FileField
from django.utils.translation import ugettext_lazy as _, ugettext as __

from dojango import forms
from freenasUI import choices
from freenasUI.contrib.IPAddressField import IP4AddressFormField
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common.warden import (Warden,
    WARDEN_KEY_HOST, WARDEN_KEY_TYPE, WARDEN_KEY_STATUS,
    WARDEN_TYPE_PLUGINJAIL, WARDEN_STATUS_RUNNING)
from freenasUI.freeadmin.views import JsonResp
from freenasUI.freeadmin.forms import PathField
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import Alias, Interfaces
from freenasUI.plugins import models
from freenasUI.storage.models import MountPoint
from freenasUI.system.forms import (
    clean_path_execbit, clean_path_locked, FileWizard
)
from freenasUI.jails.models import JailsConfiguration

log = logging.getLogger('plugins.forms')


def _clean_jail_ipv4address(jip):
    if Alias.objects.filter(alias_v4address=jip).exists() or \
        Interfaces.objects.filter(int_ipv4address=jip).exists():
        raise forms.ValidationError(_("This IP is already in use."))
    return jip


class PluginsForm(ModelForm):

    class Meta:
        model = models.Plugins
        exclude = ('plugin_pbiname', 'plugin_arch', 'plugin_version',
            'plugin_path', 'plugin_key', 'plugin_secret')

    def __init__(self, *args, **kwargs):
        super(PluginsForm, self).__init__(*args, **kwargs)
        self.instance._original_plugin_enabled = self.instance.plugin_enabled

    def save(self):
        super(PluginsForm, self).save()
        notifier()._restart_plugins(self.instance.plugin_name)


class PBIUploadForm(Form):
    pbifile = FileField(label=_("PBI file to be installed"), required=True)
    pjail = forms.ChoiceField(
        label=_("Plugin Jail"),
        help_text=_("The plugin jail that the PBI is to be installed in."),
        choices=(),
        widget=forms.Select(attrs={'class': 'required'}),
        )

    def __init__(self, *args, **kwargs):
        self.jail = None
        if kwargs and kwargs.has_key('jail'):
            self.jail = kwargs.pop('jail')

        super(PBIUploadForm, self).__init__(*args, **kwargs)

        if not self.jail:
            jc = JailsConfiguration.objects.order_by("-id")[0]
            try:
                clean_path_execbit(jc.jc_path)
            except forms.ValidationError, e:
                self.errors['__all__'] = self.error_class(e.messages)

            pjlist = []
            wlist = Warden().list()
            for wj in wlist:
                if wj[WARDEN_KEY_TYPE] == WARDEN_TYPE_PLUGINJAIL and \
                    wj[WARDEN_KEY_STATUS] == WARDEN_STATUS_RUNNING:
                    pjlist.append(wj[WARDEN_KEY_HOST])

            self.fields['pjail'].choices = [(pj, pj) for pj in pjlist ]

        else:
            self.fields['pjail'].choices = [(self.jail.jail_host, self.jail.jail_host)]
            self.fields['pjail'].widget.attrs = {
                'readonly': True,
                'class': (
                    'dijitDisabled dijitTextBoxDisabled'
                    ' dijitValidationTextBoxDisabled'
                ),
            }

    def clean(self):
        cleaned_data = self.cleaned_data
        filename = '/var/tmp/firmware/pbifile.pbi'
        if cleaned_data.get('pbifile'):
            if hasattr(cleaned_data['pbifile'], 'temporary_file_path'):
                shutil.move(
                    cleaned_data['pbifile'].temporary_file_path(),
                    filename
                    )
            else:
                with open(filename, 'wb+') as sp:
                    for c in cleaned_data['pbifile'].chunks():
                        sp.write(c)
        else:
            self._errors["pbifile"] = self.error_class([
                _("This field is required."),
                ])
        return cleaned_data

    def done(self, *args, **kwargs):
        newplugin = []
        pjail = self.cleaned_data.get('pjail')
        if notifier().install_pbi(pjail, newplugin):
            newplugin = newplugin[0]
            notifier()._restart_plugins(newplugin.plugin_jail,
                newplugin.plugin_name)


class PBIUpdateForm(PBIUploadForm):
    def __init__(self, *args, **kwargs):
        self.plugin = None
        if kwargs and kwargs.has_key('plugin'):
            self.plugin = kwargs.pop('plugin') 

        super(PBIUpdateForm, self).__init__(*args, **kwargs)

        self.fields['pjail'].initial = self.plugin.plugin_jail
        self.fields['pjail'].widget.attrs = {
            'readonly': True,
            'class': (
                'dijitDisabled dijitTextBoxDisabled'
                ' dijitValidationTextBoxDisabled'
            ),
        }

    def done(self, *args, **kwargs):
        notifier().update_pbi(self.plugin)
        notifier()._restart_plugins(self.plugin.plugin_jail,
            self.plugin.plugin_name)
