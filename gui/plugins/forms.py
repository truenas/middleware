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
import requests
import shutil
import middlewared.logger

from django.forms import FileField, MultipleChoiceField
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.common import pbi
from freenasUI.common.forms import ModelForm, Form
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import Alias, Interfaces
from freenasUI.plugins import models
from freenasUI.jails.utils import new_default_plugin_jail

log = middlewared.logger.Logger('plugins.forms')


def _clean_jail_ipv4address(jip):
    if (
        Alias.objects.filter(alias_v4address=jip).exists() or
        Interfaces.objects.filter(int_ipv4address=jip).exists()
    ):
        raise forms.ValidationError(_("This IP is already in use."))
    return jip


class PluginsForm(ModelForm):

    class Meta:
        model = models.Plugins
        exclude = (
            'plugin_pbiname', 'plugin_arch', 'plugin_version',
            'plugin_path', 'plugin_key', 'plugin_secret',
        )

    def __init__(self, *args, **kwargs):
        super(PluginsForm, self).__init__(*args, **kwargs)
        self.instance._original_plugin_enabled = self.instance.plugin_enabled

    def save(self):
        super(PluginsForm, self).save()
        notifier()._restart_plugins(
            jail=self.instance.plugin_jail,
            plugin=self.instance.plugin_name
        )

    def delete(self, request=None, events=None):
        super(PluginsForm, self).delete(request=request, events=events)
        if events is not None:
            events.append('reloadHttpd()')


class PBIUploadForm(Form):
    pbifile = FileField(
        label=_("PBI file to be installed"),
        help_text=_(
            "Click here to find out what PBI's are!"
            "<a href='http://www.pcbsd.org/en/package-management/' "
            "onclick='window.open(this.href);return false;'>"
        ),
        required=True
    )

    def __init__(self, *args, **kwargs):
        self.jail = None
        if kwargs and 'jail' in kwargs:
            self.jail = kwargs.pop('jail')

        super(PBIUploadForm, self).__init__(*args, **kwargs)

        if self.jail:
            self.fields['pjail'] = forms.ChoiceField(
                label=_("Plugin Jail"),
                help_text=_("The plugin jail that the PBI is to be installed in."),
                choices=(
                    (self.jail.jail_host, self.jail.jail_host),
                ),
                widget=forms.Select(attrs={
                    'class': (
                        'requireddijitDisabled dijitTextBoxDisabled '
                        'dijitValidationTextBoxDisabled'
                    ),
                    'readonly': True,
                }),
                required=False,
            )

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
        jail = None
        if not pjail:
            # FIXME: Better base name, using pbi_info
            try:
                jail = new_default_plugin_jail("customplugin")
            except MiddlewareError, e:
                raise e
            except Exception, e:
                raise MiddlewareError(e)

            pjail = jail.jail_host
        if notifier().install_pbi(pjail, newplugin):
            newplugin = newplugin[0]
            notifier()._restart_plugins(
                jail=newplugin.plugin_jail,
                plugin=newplugin.plugin_name,
            )
        elif jail:
            jail.delete()


class PBIUpdateForm(PBIUploadForm):
    def __init__(self, *args, **kwargs):
        self.plugin = None
        if kwargs and 'plugin' in kwargs:
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
        notifier()._restart_plugins(
            jail=self.plugin.plugin_jail,
            plugin=self.plugin.plugin_name)


class PluginUpdateForm(Form):
    jails = MultipleChoiceField(required=True)

    def __init__(self, *args, **kwargs):
        kwargs.pop('oid')
        super(PluginUpdateForm, self).__init__(*args, **kwargs)

        # plugins = get_installed_plugins_by_remote_oid(oid)
        # self.fields['jails'].choices = [(p.plugin_jail, p.plugin_jail) for p in plugins]


class ConfigurationForm(ModelForm):

    class Meta:
        model = models.Configuration

    def __init__(self, *args, **kwargs):
        super(ConfigurationForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            self._orig = dict(self.instance.__dict__)
        else:
            self._orig = {}

    def clean_repourl(self):
        repourl = self.cleaned_data.get('repourl')
        if self._orig.get('repourl') != repourl:
            try:
                r = requests.get(repourl, stream=True, verify=False, timeout=5)
                with open('/var/tmp/plugins.rpo', 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
            except Exception, e:
                raise forms.ValidationError(
                    _('Unable to set repository: %s') % e
                )
        return repourl

    def save(self, *args, **kwargs):
        obj = super(ConfigurationForm, self).save(*args, **kwargs)
        if self._orig.get('repourl') != obj.repourl:
            p = pbi.PBI()
            p.set_appdir("/var/pbi")
            for repoid, name in p.listrepo():
                p.deleterepo(repoid=repoid)
            p.addrepo(repofile='/var/tmp/plugins.rpo')
        return obj
