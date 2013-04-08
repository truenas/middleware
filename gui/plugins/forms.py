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
from freenasUI.services.models import PluginsJail
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


class JailInstallWizard(FileWizard):

    def get_template_names(self):
        return ["plugins/jailpbi.html"]

    def done(self, form_list, **kwargs):
        #jailinfo = wizard.get_cleaned_data_for_step(1)
        jailinfo = self.get_all_cleaned_data()
        pbifile = jailinfo.get("pbifile")
        pbipath = self.file_storage.path(pbifile.file.name)

        # Create a plugins service entry
        pj = PluginsJail()
        pj.jail_path = jailinfo.get('jail_path')
        pj.jail_name = jailinfo.get('jail_name')
        pj.jail_ipv4address = jailinfo.get('jail_ipv4address')
        pj.jail_ipv4netmask = jailinfo.get('jail_ipv4netmask')
        pj.plugins_path = jailinfo.get('plugins_path')

        # Install the jail PBI
        if notifier().install_jail_pbi(pj.jail_path,
                pj.jail_name,
                pj.plugins_path,
                pbipath=pbipath):
            pj.save()

        retval = getattr(self, 'retval', None)
        events = []
        if not retval:
            events.append('reloadHttpd()')
        return JsonResp(self.request,
            error=bool(retval),
            message=retval if retval else __("PBI successfully installed."),
            events=events,
            )


class JailUpdateWizard(FileWizard):

    def get_template_names(self):
        return ["plugins/jailpbi_update.html"]

    def done(self, form_list, **kwargs):
        jailinfo = self.get_all_cleaned_data()
        pbifile = jailinfo.get("pbifile")
        pbipath = self.file_storage.path(pbifile.file.name)

        pj = PluginsJail.objects.order_by("-id")[0]
        notifier().update_jail_pbi(pj.plugins_path, pbipath)

        retval = getattr(self, 'retval', None)
        events = []
        if not retval:
            events.append('reloadHttpd()')
        return JsonResp(self.request,
            error=bool(retval),
            message=retval if retval else __("PBI successfully installed."),
            events=events,
            )


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


class PBITemporaryLocationForm(Form):
    mountpoint = forms.ChoiceField(
        label=_("Place to temporarily place PBI file"),
        help_text=_("The system will use this place to temporarily store the "
            "PBI file before it's installed."),
        choices=(),
        widget=forms.Select(attrs={'class': 'required'}),
        )

    def __init__(self, *args, **kwargs):
        super(PBITemporaryLocationForm, self).__init__(*args, **kwargs)
        mp = PluginsJail.objects.order_by("-id")
        if mp and notifier().plugins_jail_configured():
            mp = mp[0]
            self.fields['mountpoint'].choices = [
                (mp.plugins_path, mp.plugins_path),
                ]
        else:
            self.fields['mountpoint'].choices = [(x.mp_path, x.mp_path) \
                for x in MountPoint.objects.exclude(
                    mp_volume__vol_fstype='iscsi')]

    def clean_mountpoint(self):
        mp = self.cleaned_data.get("mountpoint")
        clean_path_execbit(mp)
        clean_path_locked(mp)
        return mp

    def done(self, *args, **kwargs):
        notifier().change_upload_location(
            self.cleaned_data["mountpoint"].__str__()
            )


class PBIUploadForm(Form):
    pbifile = FileField(label=_("PBI file to be installed"), required=True)
    pjail = forms.ChoiceField(
        label=_("Plugin Jail"),
        help_text=_("The plugin jail that the PBI is to be installed in."),
        choices=(),
        widget=forms.Select(attrs={'class': 'required'}),
        )

    def __init__(self, *args, **kwargs):
        super(PBIUploadForm, self).__init__(*args, **kwargs)

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
        pjail = self.cleaned_data.get('pjail')
        notifier().install_pbi(pjail)
        notifier().restart("plugins")


class PBIUpdateForm(PBIUploadForm):
    def __init__(self, *args, **kwargs):
        self.plugin = kwargs.pop('plugin') 
        super(PBIUpdateForm, self).__init__(*args, **kwargs)

    def done(self, *args, **kwargs):
        notifier().update_pbi(self.plugin)
        notifier().restart("plugins")


class JailInfoForm(ModelForm):

    class Meta:
        model = PluginsJail

    def __init__(self, *args, **kwargs):
        super(JailInfoForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            for field in ('jail_path', 'jail_name', 'plugins_path'):
                self.fields[field].widget.attrs['readonly'] = True
                self.fields[field].widget.attrs['class'] = ('dijitDisabled'
                    ' dijitTextBoxDisabled dijitValidationTextBoxDisabled')

    def clean_jail_ipv4address(self):
        return _clean_jail_ipv4address(
            self.cleaned_data.get("jail_ipv4address")
            )

    def clean(self):
        cleaned_data = self.cleaned_data

        if (
                'jail_path' not in cleaned_data or
                'plugins_path' not in cleaned_data or
                'jail_name' not in cleaned_data
                ):
            return cleaned_data
        jp = cleaned_data.get('jail_path') + "/"
        pp = cleaned_data.get('plugins_path') + "/"

        if self.instance.id and notifier()._started_plugins_jail():
            self._errors['__all__'] = self.error_class([
                _("You must turn off Plugins service before proceeding"),
            ])
            return cleaned_data

        full_path = os.path.join(jp, cleaned_data.get('jail_name'))
        if not self.instance.id and os.path.exists(full_path):
            self._errors['__all__'] = self.error_class([
                _("The path %s already exists") % (full_path, ),
            ])

        # See #1341 and PR/161481, +12 is for additional /mnt/plugins nullfs
        if len(full_path) + 12 > 88:
            self._errors['jail_path'] = self.error_class([
                _("The full jail path cannot exceed 76 characters"),
            ])

        try:
            # TODO: This could be improved checking whether the paths exists
            samefs = os.stat(jp).st_dev == os.stat(pp).st_dev
        except OSError:
            samefs = True

        if (jp in pp and samefs):
            self._errors["jail_path"] = self.error_class([
                _("The plugins jail path cannot be a subset of the plugins "
                    "archive path."),
                ])
        if (pp in jp and samefs):
            self._errors["plugins_path"] = self.error_class([
                _("The plugins archive path cannot be a subset of the plugins "
                    "jail path."),
                ])

        return cleaned_data


class JailImportForm(Form):
    jail_import_path = PathField(
            label=_("Plugins jail path"),
            required=True,
            )
    jail_import_ipv4address = IP4AddressFormField(
            label=_("Jail IPv4 Address"),
            required=True,
            )
    jail_import_ipv4netmask = forms.ChoiceField(
            label=_("Jail IPv4 Netmask"),
            initial="24",
            choices=choices.v4NetmaskBitList,
            required=True,
            )
    plugins_import_path = PathField(
            label=_("Plugins archive Path"),
            required=True,
            )

    def __init__(self, *args, **kwargs):
        super(JailImportForm, self).__init__(*args, **kwargs)

    def clean_jail_import_ipv4address(self):
        return _clean_jail_ipv4address(
            self.cleaned_data.get("jail_import_ipv4address")
        )


class JailPBIUploadForm(Form):

    pbifile = FileField(
            label=_("Plugins Jail PBI"),
            required=True
            )


class NullMountPointForm(ModelForm):

    mounted = forms.BooleanField(
        label=_("Mounted?"),
        required=False,
        initial=True,
        )

    class Meta:
        model = models.NullMountPoint
        widgets = {
            'source': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
                }),
            'destination': forms.widgets.TextInput(attrs={
                'data-dojo-type': 'freeadmin.form.PathSelector',
                }),
        }

    def clean_source(self):
        src = self.cleaned_data.get("source")
        src = os.path.abspath(src.strip().replace("..", ""))
        return src

    def clean_destination(self):
        dest = self.cleaned_data.get("destination")
        dest = os.path.abspath(dest.strip().replace("..", ""))
        jail = PluginsJail.objects.order_by('-id')[0]
        full = "%s/%s%s" % (jail.jail_path, jail.jail_name, dest)
        if len(full) > 88:
            raise forms.ValidationError(
                _("The full path cannot exceed 88 characters")
                )
        return dest

    def __init__(self, *args, **kwargs):
        super(NullMountPointForm, self).__init__(*args, **kwargs)
        jail = PluginsJail.objects.order_by("-pk")[0]
        self.fields['destination'].widget.attrs['root'] = (
                os.path.join(jail.jail_path, jail.jail_name)
            )
        if self.instance.id:
            self.fields['mounted'].initial = self.instance.mounted
        else:
            self.fields['mounted'].widget = forms.widgets.HiddenInput()

    def save(self, *args, **kwargs):
        obj = super(NullMountPointForm, self).save(*args, **kwargs)
        mounted = self.cleaned_data.get("mounted")
        if mounted == obj.mounted:
            return obj
        if mounted and not obj.mount():
            #FIXME better error handling, show the user why
            raise MiddlewareError(_("The path could not be mounted %s") % (
                obj.source,
                ))
        if not mounted and not obj.umount():
            #FIXME better error handling, show the user why
            raise MiddlewareError(_("The path could not be umounted %s") % (
                obj.source,
                ))
        return obj
