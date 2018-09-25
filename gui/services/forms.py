# Copyright 2010 iXsystems, Inc.
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
import re

from django.db.models import Q
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from dojango import forms
from freenasUI import choices
from freenasUI.common.forms import Form, ModelForm
from freenasUI.common.freenassysctl import freenas_sysctl as _fs
from freenasUI.common.system import activedirectory_enabled, ldap_enabled
from freenasUI.freeadmin.forms import DirectoryBrowser
from freenasUI.freeadmin.options import FreeBaseInlineFormSet
from freenasUI.freeadmin.utils import key_order
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.middleware.notifier import notifier
from freenasUI.network.models import Alias, Interfaces
from freenasUI.services import models
from freenasUI.storage.widgets import UnixPermissionField
from freenasUI.support.utils import fc_enabled
from middlewared.plugins.iscsi import AUTHMETHOD_LEGACY_MAP
from middlewared.plugins.smb import LOGLEVEL_MAP
from freenasUI.middleware.client import client

log = logging.getLogger('services.form')


class servicesForm(ModelForm):
    """
    This form is only used for API 1.0 compatibility
    Services view now uses middlewared directly.
    """

    class Meta:
        fields = '__all__'
        model = models.services

    def save(self, *args, **kwargs):
        obj = super(servicesForm, self).save(*args, **kwargs)
        _notifier = notifier()

        if obj.srv_service == 'cifs' and _notifier.started('domaincontroller'):
            obj.srv_enable = True
            obj.save()
            started = True

        elif obj.srv_service == 'domaincontroller':
            if obj.srv_enable is True:
                if _notifier.started('domaincontroller'):
                    started = _notifier.restart("domaincontroller",
                                                timeout=_fs().services.domaincontroller.timeout.restart)
                else:
                    started = _notifier.start("domaincontroller",
                                              timeout=_fs().services.domaincontroller.timeout.start)
            else:
                started = _notifier.stop("domaincontroller",
                                         timeout=_fs().services.domaincontroller.timeout.stop)

        else:
            """
            For now on, lets handle it properly for all services!
            """
            if obj.srv_enable:
                started = _notifier.start(obj.srv_service)
            else:
                started = _notifier.stop(obj.srv_service)

        self.started = started
        if started is True:
            if not obj.srv_enable:
                obj.srv_enable = True
                obj.save()

        elif started is False:
            if obj.srv_enable:
                obj.srv_enable = False
                obj.save()

        return obj


class CIFSForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "cifs_srv_"
    middleware_attr_schema = "smb"
    middleware_plugin = "smb"
    is_singletone = True

    cifs_srv_bindip = forms.MultipleChoiceField(
        label=models.CIFS._meta.get_field('cifs_srv_bindip').verbose_name,
        help_text=models.CIFS._meta.get_field('cifs_srv_bindip').help_text,
        required=False,
        widget=forms.widgets.CheckedMultiSelect(),
    )
    cifs_srv_unixcharset = forms.ChoiceField(
        label=models.CIFS._meta.get_field('cifs_srv_unixcharset').verbose_name,
        required=False,
        initial='UTF-8'
    )
    cifs_srv_doscharset = forms.ChoiceField(
        label=models.CIFS._meta.get_field('cifs_srv_doscharset').verbose_name,
        required=False,
        initial='CP437'
    )

    class Meta:
        fields = '__all__'
        exclude = ['cifs_SID', 'cifs_srv_bindip']
        model = models.CIFS

    def __init__(self, *args, **kwargs):
        super(CIFSForm, self).__init__(*args, **kwargs)
        if self.data and self.data.get('cifs_srv_bindip'):
            if ',' in self.data['cifs_srv_bindip']:
                self.data = self.data.copy()
                self.data.setlist(
                    'cifs_srv_bindip',
                    self.data['cifs_srv_bindip'].split(',')
                )

        self.fields['cifs_srv_bindip'].choices = list(choices.IPChoices(noloopback=False))
        self.fields['cifs_srv_unixcharset'].choices = choices.UNIXCHARSET_CHOICES()
        self.fields['cifs_srv_doscharset'].choices = choices.DOSCHARSET_CHOICES()

        if self.instance.id and self.instance.cifs_srv_bindip:
            bindips = []
            for ip in self.instance.cifs_srv_bindip:
                bindips.append(ip)

            self.fields['cifs_srv_bindip'].initial = (bindips)
        else:
            self.fields['cifs_srv_bindip'].initial = ('')

        # Disable UNIX extensions if not using SMB1 - We can probably disable other things too
        proto = _fs().services.smb.config.server_min_protocol
        if re.match('SMB[23]+', proto):
            self.initial['cifs_srv_unixext'] = False
            self.fields['cifs_srv_unixext'].widget.attrs['disabled'] = 'disabled'

        if activedirectory_enabled():
            self.initial['cifs_srv_localmaster'] = False
            self.fields['cifs_srv_localmaster'].widget.attrs['disabled'] = 'disabled'
            self.initial['cifs_srv_timeserver'] = False
            self.fields['cifs_srv_timeserver'].widget.attrs['disabled'] = 'disabled'
            self.initial['cifs_srv_domain_logons'] = False
            self.fields['cifs_srv_domain_logons'].widget.attrs['disabled'] = 'disabled'

        elif ldap_enabled():
            self.initial['cifs_srv_domain_logons'] = True
            self.fields['cifs_srv_domain_logons'].widget.attrs['readonly'] = True

        _n = notifier()
        if not _n.is_freenas():
            if not _n.failover_licensed():
                del self.fields['cifs_srv_netbiosname_b']
            else:
                from freenasUI.failover.utils import node_label_field
                node_label_field(
                    _n.failover_node(),
                    self.fields['cifs_srv_netbiosname'],
                    self.fields['cifs_srv_netbiosname_b'],
                )
        else:
            del self.fields['cifs_srv_netbiosname_b']

    def middleware_clean(self, data):
        if 'loglevel' in data:
            data['loglevel'] = LOGLEVEL_MAP.get(data['loglevel'])
        return data


class AFPForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "afp_srv_"
    middleware_attr_schema = "afp"
    middleware_plugin = "afp"
    is_singletone = True

    afp_srv_bindip = forms.MultipleChoiceField(
        label=models.AFP._meta.get_field('afp_srv_bindip').verbose_name,
        help_text=models.AFP._meta.get_field('afp_srv_bindip').help_text,
        required=False,
        widget=forms.widgets.CheckedMultiSelect(),
    )

    class Meta:
        fields = '__all__'
        exclude = ['afp_SID', 'afp_srv_bindip']
        model = models.AFP

    def __init__(self, *args, **kwargs):
        super(AFPForm, self).__init__(*args, **kwargs)
        if self.data and self.data.get('afp_srv_bindip'):
            if ',' in self.data['afp_srv_bindip']:
                self.data = self.data.copy()
                self.data.setlist(
                    'afp_srv_bindip',
                    self.data['afp_srv_bindip'].split(',')
                )
        self.fields['afp_srv_bindip'].choices = list(choices.IPChoices())
        if self.instance.id and self.instance.afp_srv_bindip:
            bindips = []
            for ip in self.instance.afp_srv_bindip:
                bindips.append(ip)

            self.fields['afp_srv_bindip'].initial = (bindips)
        else:
            self.fields['afp_srv_bindip'].initial = ('')


class NFSForm(MiddlewareModelForm, ModelForm):

    middleware_attr_map = {
        'userd_manage_gids': 'nfs_srv_16',
    }
    middleware_attr_prefix = "nfs_srv_"
    middleware_attr_schema = "nfs"
    middleware_plugin = "nfs"
    is_singletone = True

    class Meta:
        model = models.NFS
        fields = '__all__'
        widgets = {
            'nfs_srv_mountd_port': forms.widgets.TextInput(),
            'nfs_srv_rpcstatd_port': forms.widgets.TextInput(),
            'nfs_srv_rpclockd_port': forms.widgets.TextInput(),
            'nfs_srv_bindip': forms.widgets.CheckedMultiSelect(),
        }

    def __init__(self, *args, **kwargs):
        super(NFSForm, self).__init__(*args, **kwargs)
        if self.data and self.data.get('nfs_srv_bindip'):
            if ',' in self.data['nfs_srv_bindip']:
                self.data = self.data.copy()
                self.data.setlist(
                    'nfs_srv_bindip',
                    self.data['nfs_srv_bindip'].split(',')
                )
        self.fields['nfs_srv_bindip'].choices = list(choices.IPChoices())
        if self.instance.id and self.instance.nfs_srv_bindip:
            bindips = []
            for ip in self.instance.nfs_srv_bindip:
                bindips.append(ip)

            self.fields['nfs_srv_bindip'].initial = bindips
        else:
            self.fields['nfs_srv_bindip'].initial = ''
        key_order(self, 2, 'nfs_srv_bindip', instance=True)

        self.fields['nfs_srv_mountd_port'].label = (
            self.fields['nfs_srv_mountd_port'].label.lower()
        )
        self.fields['nfs_srv_rpcstatd_port'].label = (
            self.fields['nfs_srv_rpcstatd_port'].label.lower()
        )
        self.fields['nfs_srv_rpclockd_port'].label = (
            self.fields['nfs_srv_rpclockd_port'].label.lower()
        )
        self.instance._original_nfs_srv_v4 = self.instance.nfs_srv_v4
        self.fields['nfs_srv_v4'].widget.attrs['onChange'] = (
            'javascript:toggleNFSService();'
        )
        self.fields['nfs_srv_v4_v3owner'].widget.attrs['onChange'] = (
            'javascript:toggleNFSService();'
        )
        self.fields['nfs_srv_16'].widget.attrs['onChange'] = (
            'javascript:toggleNFSService();'
        )
        if not self.instance.nfs_srv_v4 or (self.instance.nfs_srv_v4 and self.instance.nfs_srv_16):
            self.fields['nfs_srv_v4_v3owner'].widget.attrs['disabled'] = (
                'disabled'
            )
        if self.instance.nfs_srv_v4_v3owner:
            self.fields['nfs_srv_16'].widget.attrs['disabled'] = 'disabled'

    def middleware_clean(self, update):
        update['userd_manage_gids'] = update.pop('16')
        return update


class FTPForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "ftp_"
    middleware_attr_schema = "ftp"
    middleware_plugin = "ftp"
    is_singletone = True

    ftp_filemask = UnixPermissionField(label=_('File Permission'))
    ftp_dirmask = UnixPermissionField(label=_('Directory Permission'))

    class Meta:
        fields = '__all__'
        model = models.FTP
        widgets = {
            'ftp_port': forms.widgets.TextInput(),
            'ftp_passiveportsmin': forms.widgets.TextInput(),
            'ftp_passiveportsmax': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):

        if 'instance' in kwargs:
            instance = kwargs['instance']
            try:
                mask = int(instance.ftp_filemask, 8)
                instance.ftp_filemask = "%.3o" % (~mask & 0o666)
            except ValueError:
                pass

            try:
                mask = int(instance.ftp_dirmask, 8)
                instance.ftp_dirmask = "%.3o" % (~mask & 0o777)
            except ValueError:
                pass

        super(FTPForm, self).__init__(*args, **kwargs)

    def clean_ftp_filemask(self):
        perm = self.cleaned_data['ftp_filemask']
        perm = int(perm, 8)
        mask = (~perm & 0o666)
        return "%.3o" % mask

    def clean_ftp_dirmask(self):
        perm = self.cleaned_data['ftp_dirmask']
        perm = int(perm, 8)
        mask = (~perm & 0o777)
        return "%.3o" % mask


class TFTPForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "tftp_"
    middleware_attr_schema = "tftp"
    middleware_plugin = "tftp"
    is_singletone = True

    tftp_umask = UnixPermissionField(label=_('File Permission'))

    class Meta:
        fields = '__all__'
        model = models.TFTP
        widgets = {
            'tftp_port': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):

        if 'instance' in kwargs:
            instance = kwargs['instance']
            try:
                mask = int(instance.tftp_umask, 8)
                instance.tftp_umask = "%.3o" % (~mask & 0o666)
            except ValueError:
                pass

        super(TFTPForm, self).__init__(*args, **kwargs)

    def clean_tftp_umask(self):
        perm = self.cleaned_data['tftp_umask']
        perm = int(perm, 8)
        mask = (~perm & 0o666)
        return "%.3o" % mask


class SSHForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'ssh_'
    middleware_attr_schema = 'ssh'
    middleware_plugin = 'ssh'
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.SSH
        widgets = {
            'ssh_tcpport': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(SSHForm, self).__init__(*args, **kwargs)
        self.fields['ssh_bindiface'].choices = list(choices.NICChoices(exclude_configured=False,
                                                    exclude_unconfigured_vlan_parent=True))


class RsyncdForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "rsyncd_"
    middleware_attr_schema = "rsyncd"
    middleware_plugin = "rsyncd"

    class Meta:
        fields = '__all__'
        model = models.Rsyncd


class RsyncModForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "rsyncmod_"
    middleware_attr_schema = "rsyncmod"
    middleware_plugin = "rsyncmod"
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.RsyncMod

    def middleware_clean(self, update):
        update['hostsallow'] = update["hostsallow"].split()
        update['hostsdeny'] = update["hostsdeny"].split()
        return update


class DynamicDNSForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = "ddns_"
    middleware_attr_schema = "dyndns"
    middleware_exclude_fields = ["password2"]
    middleware_plugin = "dyndns"
    is_singletone = True

    ddns_password2 = forms.CharField(
        max_length=50,
        label=_("Confirm Password"),
        widget=forms.widgets.PasswordInput(),
        required=False,
    )

    class Meta:
        model = models.DynamicDNS
        widgets = {
            'ddns_password': forms.widgets.PasswordInput(render_value=False),
            'ddns_period': forms.widgets.TextInput(attrs={"placeholder": 300}),
        }
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(DynamicDNSForm, self).__init__(*args, **kwargs)
        self.fields['ddns_provider'].widget.attrs['onChange'] = (
            "ddnsCustomProviderToggle();"
        )
        if self.instance.ddns_password:
            self.fields['ddns_password'].required = False
        self.fields['ddns_period'].required = False
        if self._api is True:
            del self.fields['ddns_password2']

    def clean_ddns_password2(self):
        password1 = self.cleaned_data.get("ddns_password")
        password2 = self.cleaned_data.get("ddns_password2")
        if password1 != password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return password2

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("ddns_password"):
            cdata['ddns_password'] = self.instance.ddns_password
        return cdata

    def middleware_clean(self, update):
        update["domain"] = update["domain"].split()
        return update


key_order(DynamicDNSForm, 10, 'ddns_password2')


class SNMPForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "snmp_"
    middleware_attr_schema = "snmp"
    middleware_exclude_fields = ["v3_password2", "v3_privpassphrase2"]
    middleware_plugin = "snmp"
    is_singletone = True

    snmp_v3_password2 = forms.CharField(
        max_length=40,
        label=_("Confirm Password"),
        widget=forms.widgets.PasswordInput(render_value=True),
        required=False,
    )

    snmp_v3_privpassphrase2 = forms.CharField(
        max_length=40,
        label=_("Confirm Privacy Passphrase"),
        widget=forms.widgets.PasswordInput(render_value=True),
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.SNMP
        widgets = {
            'snmp_v3_password': forms.widgets.PasswordInput(render_value=True),
            'snmp_v3_privpassphrase': forms.widgets.PasswordInput(
                render_value=True
            ),
        }

    def __init__(self, *args, **kwargs):
        super(SNMPForm, self).__init__(*args, **kwargs)
        self.fields['snmp_v3'].widget.attrs['onChange'] = (
            'toggleGeneric("id_snmp_v3", ["id_snmp_v3_password", '
            '"id_snmp_v3_password2", "id_snmp_v3_username", '
            '"id_snmp_v3_authtype", "id_snmp_v3_privproto", '
            '"id_snmp_v3_privpassphrase", "id_snmp_v3_privpassphrase2"],true);'
        )
        if self.instance.id and not self.instance.snmp_v3:
            self.fields['snmp_v3_password'].widget.attrs['disabled'] = (
                'disabled'
            )
            self.fields['snmp_v3_password2'].widget.attrs['disabled'] = (
                'disabled'
            )
            self.fields['snmp_v3_authtype'].widget.attrs['disabled'] = (
                'disabled'
            )
            self.fields['snmp_v3_username'].widget.attrs['disabled'] = (
                'disabled'
            )
            self.fields['snmp_v3_privproto'].widget.attrs['disabled'] = (
                'disabled'
            )
            self.fields['snmp_v3_privpassphrase'].widget.attrs['disabled'] = (
                'disabled'
            )
            self.fields['snmp_v3_privpassphrase2'].widget.attrs['disabled'] = (
                'disabled'
            )
        if self.instance.id:
            self.fields['snmp_v3_password2'].initial = self.instance.snmp_v3_password
            self.fields['snmp_v3_privpassphrase2'].initial = self.instance.snmp_v3_privpassphrase

    def clean_snmp_v3_password2(self):
        password1 = self.cleaned_data.get("snmp_v3_password")
        password2 = self.cleaned_data.get("snmp_v3_password2")
        if not password1:
            return password2
        if password1 != password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return password2

    def clean_snmp_v3_privpassphrase2(self):
        passphrase1 = self.cleaned_data.get("snmp_v3_privpassphrase")
        passphrase2 = self.cleaned_data.get("snmp_v3_privpassphrase2")
        if not passphrase1:
            return passphrase2
        if passphrase1 != passphrase2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return passphrase2


key_order(SNMPForm, 7, 'snmp_v3_password2')
key_order(SNMPForm, 10, 'snmp_v3_privpassphrase2')


class UPSForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "ups_"
    middleware_attr_schema = "ups"
    middleware_plugin = "ups"
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.UPS
        widgets = {
            'ups_remoteport': forms.widgets.TextInput(),
            'ups_driver': forms.widgets.FilteringSelect(),
            'ups_nocommwarntime': forms.widgets.TextInput(),
            'ups_monpwd': forms.widgets.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super(UPSForm, self).__init__(*args, **kwargs)
        _n = notifier()
        if not _n.is_freenas():
            self.fields['ups_powerdown'].help_text = _("Signal the UPS to power off after TrueNAS shuts down.")
        self.fields['ups_shutdown'].widget.attrs['onChange'] = mark_safe(
            "disableGeneric('id_ups_shutdown', ['id_ups_shutdowntimer'], "
            "function(box) { if(box.get('value') == 'lowbatt') { return true; "
            "} else { return false; } });")
        self.fields['ups_mode'].widget.attrs['onChange'] = "upsModeToggle();"
        if self.instance.id and self.instance.ups_shutdown == 'lowbatt':
            self.fields['ups_shutdowntimer'].widget.attrs['class'] = (
                'dijitDisabled dijitTextBoxDisabled '
                'dijitValidationTextBoxDisabled')

        self.fields['ups_port'] = forms.ChoiceField(
            label=_("Port"),
            required=False,
        )
        self.fields['ups_port'].widget = forms.widgets.ComboBox()
        self.fields['ups_port'].choices = choices.UPS_PORT_CHOICES()
        if self.data and self.data.get("ups_port"):
            self.fields['ups_port'].choices.insert(
                0, (self.data.get("ups_port"), self.data.get("ups_port"))
            )
        elif self.instance.id:
            self.fields['ups_port'].choices.insert(
                0, (self.instance.ups_port, self.instance.ups_port)
            )

    def middleware_clean(self, data):
        data['toemail'] = [v.strip() for v in data['toemail'].split(';') if v]
        data['shutdown'] = data['shutdown'].upper()
        data['mode'] = data['mode'].upper()
        return data


class LLDPForm(MiddlewareModelForm, ModelForm):

    class Meta:
        fields = '__all__'
        model = models.LLDP

    middleware_attr_prefix = "lldp_"
    middleware_attr_schema = "lldp"
    middleware_plugin = "lldp"
    is_singletone = True


class iSCSITargetAuthCredentialForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = "iscsi_target_auth_"
    middleware_attr_schema = "services.iscsi_targetauthcredential"
    middleware_plugin = "iscsi.auth"
    is_singletone = False

    iscsi_target_auth_secret2 = forms.CharField(
        label=_("Secret (Confirm)"),
        widget=forms.PasswordInput(render_value=True),
        help_text=_("Enter the same secret above for verification.")
    )
    iscsi_target_auth_peersecret2 = forms.CharField(
        label=_("Peer Secret (Confirm)"),
        widget=forms.PasswordInput(render_value=True),
        help_text=_("Enter the same secret above for verification."),
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.iSCSITargetAuthCredential
        widgets = {
            'iscsi_target_auth_secret': forms.PasswordInput(render_value=True),
            'iscsi_target_auth_peersecret': forms.PasswordInput(
                render_value=True
            ),
        }

    def __init__(self, *args, **kwargs):
        super(iSCSITargetAuthCredentialForm, self).__init__(*args, **kwargs)
        if self._api:
            del self.fields['iscsi_target_auth_secret2']
            del self.fields['iscsi_target_auth_peersecret2']
        else:
            key_order(self, 3, 'iscsi_target_auth_secret2', instance=True)
            key_order(self, 6, 'iscsi_target_auth_peersecret2', instance=True)

            ins = kwargs.get("instance", None)
            if ins:
                self.fields['iscsi_target_auth_secret2'].initial = (
                    self.instance.iscsi_target_auth_secret)
                self.fields['iscsi_target_auth_peersecret2'].initial = (
                    self.instance.iscsi_target_auth_peersecret)

    def _clean_secret_common(self, secretprefix):
        secret1 = self.cleaned_data.get(secretprefix, "")
        secret2 = self.cleaned_data[("%s2" % secretprefix)]
        if secret1 != secret2:
            raise forms.ValidationError(_("Secret does not match"))
        return secret2

    def clean_iscsi_target_auth_secret2(self):
        return self._clean_secret_common("iscsi_target_auth_secret")

    def clean_iscsi_target_auth_peersecret2(self):
        return self._clean_secret_common("iscsi_target_auth_peersecret")

    def middleware_clean(self, data):
        data.pop('secret2', None)
        data.pop('peersecret2', None)
        return data


class iSCSITargetToExtentForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = "iscsi_"
    middleware_attr_schema = "iscsi_targetextent"
    middleware_plugin = "iscsi.targetextent"
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.iSCSITargetToExtent
        widgets = {
            'iscsi_extent': forms.widgets.FilteringSelect(),
            'iscsi_lunid': forms.widgets.TextInput(),
            'iscsi_target': forms.widgets.FilteringSelect(),
        }

    def __init__(self, *args, **kwargs):
        super(iSCSITargetToExtentForm, self).__init__(*args, **kwargs)
        self.fields['iscsi_lunid'].initial = 0
        self.fields['iscsi_lunid'].required = True


class iSCSITargetGlobalConfigurationForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "iscsi_"
    middleware_attr_schema = "iscsiglobal"
    middleware_plugin = "iscsi.global"
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.iSCSITargetGlobalConfiguration
        widgets = {
            'iscsi_pool_avail_threshold': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(iSCSITargetGlobalConfigurationForm, self).__init__(*args, **kwargs)
        _n = notifier()
        if not (not _n.is_freenas() and _n.failover_licensed()):
            del self.fields['iscsi_alua']

    def middleware_clean(self, data):
        data['isns_servers'] = data['isns_servers'].split()
        return data


class iSCSITargetExtentForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = 'iscsi_target_extent_'
    middleware_attr_schema = 'iscsi_extent'
    middleware_plugin = 'iscsi.extent'
    is_singletone = False

    iscsi_target_extent_type = forms.ChoiceField(
        choices=(
            ('Disk', _('Device')),
            ('File', _('File')),
        ),
        label=_("Extent Type"),
    )

    class Meta:
        model = models.iSCSITargetExtent
        exclude = (
            'iscsi_target_extent_type',
            'iscsi_target_extent_legacy',
        )
        widgets = {
            'iscsi_target_extent_path': DirectoryBrowser(dirsonly=False),
            'iscsi_target_extent_avail_threshold': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(iSCSITargetExtentForm, self).__init__(*args, **kwargs)
        key_order(self, 1, 'iscsi_target_extent_type', instance=True)

        if not self._api:
            self.fields['iscsi_target_extent_disk'] = forms.ChoiceField(
                choices=(),
                widget=forms.Select(attrs={'maxHeight': 200}),
                label=_('Device'),
                required=False,
            )
        else:
            self.fields['iscsi_target_extent_disk'] = forms.CharField(
                required=False,
            )

        key_order(self, 2, 'iscsi_target_extent_disk', instance=True)

        if self.instance.id:
            with client as c:
                e = self.instance.iscsi_target_extent_path
                exclude = [e] if not self._api else []

                disk_choices = list(c.call(
                    'iscsi.extent.disk_choices', exclude).items())

            if self.instance.iscsi_target_extent_type == 'File':
                self.fields['iscsi_target_extent_type'].initial = 'File'
            else:
                self.fields['iscsi_target_extent_type'].initial = 'Disk'
            if not self._api:
                self.fields['iscsi_target_extent_disk'].choices = disk_choices
            if self.instance.iscsi_target_extent_type in ('ZVOL', 'HAST'):
                self.fields['iscsi_target_extent_disk'].initial = disk_choices
            else:
                self.fields['iscsi_target_extent_disk'].initial = self.instance.get_device()[5:]
            self._path = self.instance.iscsi_target_extent_path
            self._name = self.instance.iscsi_target_extent_name
        elif not self._api:
            with client as c:
                disk_choices = list(c.call(
                    'iscsi.extent.disk_choices').items())

            self.fields['iscsi_target_extent_disk'].choices = disk_choices
        self.fields['iscsi_target_extent_type'].widget.attrs['onChange'] = "iscsiExtentToggle();extentZvolToggle();"
        self.fields['iscsi_target_extent_path'].required = False

        self.fields['iscsi_target_extent_disk'].widget.attrs['onChange'] = (
            'extentZvolToggle();'
        )

    def clean_iscsi_target_extent_filesize(self):
        size = self.cleaned_data['iscsi_target_extent_filesize']
        try:
            int(size)
        except ValueError:
            suffixes = {
                'PB': 1125899906842624,
                'TB': 1099511627776,
                'GB': 1073741824,
                'MB': 1048576,
                'KB': 1024,
                'B': 1
            }
            for x in suffixes.keys():
                if size.upper().endswith(x):
                    size = size.strip(x)

                    if not size.isdigit():
                        # They need to supply a real number
                        break

                    size = int(size) * suffixes[x]

                    return size
            raise forms.ValidationError(_("This value can be a size in bytes, or can be postfixed with KB, MB, GB, TB"))
        return size

    def middleware_clean(self, data):
        extent_type = data['type']
        extent_rpm = data['rpm']
        data['type'] = extent_type.upper()
        data['rpm'] = extent_rpm.upper()

        return data


class iSCSITargetPortalForm(MiddlewareModelForm, ModelForm):

    middleware_attr_map = {
        'discovery_authmethod': 'iscsi_target_portal_discoveryauthmethod',
        'discovery_authgroup': 'iscsi_target_portal_discoveryauthgroup',
    }
    middleware_attr_prefix = 'iscsi_target_portal_'
    middleware_attr_schema = 'iscsiportal'
    middleware_plugin = 'iscsi.portal'
    is_singletone = False

    iscsi_target_portal_discoveryauthgroup = forms.ChoiceField(
        label=_("Discovery Auth Group")
    )

    class Meta:
        fields = '__all__'
        model = models.iSCSITargetPortal
        widgets = {
            'iscsi_target_portal_tag': forms.widgets.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(iSCSITargetPortalForm, self).__init__(*args, **kwargs)
        self._listen = []
        self.fields['iscsi_target_portal_discoveryauthgroup'].required = False
        self.fields['iscsi_target_portal_discoveryauthgroup'].choices = [(None, _('None'))] + [(i['iscsi_target_auth_tag'], i['iscsi_target_auth_tag']) for i in models.iSCSITargetAuthCredential.objects.all().values('iscsi_target_auth_tag').distinct()]

    def cleanformset_iscsitargetportalip(self, fs, forms):
        for form in forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            self._listen.append({
                'ip': form.cleaned_data.get('iscsi_target_portalip_ip'),
                'port': form.cleaned_data.get('iscsi_target_portalip_port'),
            })
        return True

    def middleware_clean(self, data):
        data['listen'] = self._listen
        data['discovery_authmethod'] = AUTHMETHOD_LEGACY_MAP.get(data.pop('discoveryauthmethod'))
        data['discovery_authgroup'] = data.pop('discoveryauthgroup') or None
        data.pop('tag', None)
        return data


class iSCSITargetPortalIPForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.iSCSITargetPortalIP
        widgets = {
            'iscsi_target_portalip_port': forms.widgets.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super(iSCSITargetPortalIPForm, self).__init__(*args, **kwargs)
        self.fields['iscsi_target_portalip_ip'] = forms.ChoiceField(
            label=self.fields['iscsi_target_portalip_ip'].label,
        )
        ips = [('', '------'), ('0.0.0.0', '0.0.0.0')]
        iface_ips = {
            iface.int_vip: f'{iface.int_ipv4address}, {iface.int_ipv4address_b}'
            for iface in Interfaces.objects.exclude(Q(int_vip=None) | Q(int_vip=''))
        }
        for alias in Alias.objects.exclude(Q(alias_vip=None) | Q(alias_vip='')):
            iface_ips[alias.alias_vip] = f'{alias.alias_v4address}, {alias.alias_v4address_b}'
        for k, v in choices.IPChoices():
            if v in iface_ips:
                v = iface_ips[v]
            ips.append((k, v))

        if self.instance.id and self.instance.iscsi_target_portalip_ip not in dict(ips):
            ips.append((
                self.instance.iscsi_target_portalip_ip, self.instance.iscsi_target_portalip_ip
            ))
        self.fields['iscsi_target_portalip_ip'].choices = ips
        if not self.instance.id and not self.data:
            if not(
                self.parent and self.parent.instance.id and
                self.parent.instance.ips.all().count() > 0
            ) or (self.parent and not self.parent.instance.id):
                self.fields['iscsi_target_portalip_ip'].initial = '0.0.0.0'


class iSCSITargetPortalIPInlineFormSet(FreeBaseInlineFormSet):
    def save(self, *args, **kwargs):
        # save is done in middleware using parent form
        pass


class iSCSITargetAuthorizedInitiatorForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'iscsi_target_initiator_'
    middleware_attr_schema = 'iscsi_initiator'
    middleware_plugin = 'iscsi.initiator'
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.iSCSITargetAuthorizedInitiator
        exclude = (
            'iscsi_target_initiator_tag',
        )

    def middleware_clean(self, data):
        initiators = data['initiators']
        auth_network = data['auth_network']

        initiators = [] if initiators == 'ALL' else initiators.split()
        auth_network = [] if auth_network == 'ALL' else auth_network.split()

        data['initiators'] = initiators
        data['auth_network'] = auth_network

        return data


class iSCSITargetGroupsInlineFormSet(FreeBaseInlineFormSet):

    def clean(self):
        rv = super(iSCSITargetGroupsInlineFormSet, self).clean()
        if self._fparent.data and self._fparent.data.get(
            'iscsi_target_mode'
        ) == 'fc':
            self._errors = []
            for form in self.forms:
                form._errors = []
        return rv


class iSCSITargetForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "iscsi_target_"
    middleware_attr_schema = "iscsi_target_"
    middleware_plugin = "iscsi.target"
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.iSCSITarget
        widgets = {
            'iscsi_target_mode': forms.widgets.RadioSelect(),
        }

    def __init__(self, *args, **kwargs):
        super(iSCSITargetForm, self).__init__(*args, **kwargs)
        self._groups = []
        self.fields['iscsi_target_mode'].widget.attrs['onChange'] = (
            'targetMode();'
        )
        if not fc_enabled():
            self.fields['iscsi_target_mode'].initial = 'iscsi'
            self.fields['iscsi_target_mode'].widget = forms.widgets.HiddenInput()

    def cleanformset_iscsitargetgroups(self, fs, forms):
        for form in forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            data = {
                'authmethod': AUTHMETHOD_LEGACY_MAP.get(
                    form.cleaned_data.get('iscsi_target_authtype')
                ),
            }
            for i in ('portal', 'auth', 'initiator'):
                group = form.cleaned_data.get(f'iscsi_target_{i}group')
                if group == '-1':
                    group = None
                if group:
                    if hasattr(group, 'id'):
                        data[i] = group.id
                    else:
                        data[i] = int(group)
                else:
                    data[i] = None
            self._groups.append(data)
        return True

    def middleware_clean(self, data):
        data['mode'] = data['mode'].upper()
        data['groups'] = self._groups
        data['alias'] = data.get('alias') or None
        return data


class iSCSITargetGroupsForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "iscsi_target_"
    middleware_plugin = "iscsi.target"
    is_singletone = False

    iscsi_target_authgroup = forms.ChoiceField(label=_("Authentication Group number"))

    class Meta:
        fields = '__all__'
        model = models.iSCSITargetGroups
        exclude = ('iscsi_target_initialdigest', )

    def __init__(self, *args, **kwargs):
        super(iSCSITargetGroupsForm, self).__init__(*args, **kwargs)
        self.fields['iscsi_target_authgroup'].required = False
        self.fields['iscsi_target_authgroup'].choices = [(-1, _('None'))] + [(i['iscsi_target_auth_tag'], i['iscsi_target_auth_tag']) for i in models.iSCSITargetAuthCredential.objects.all().values('iscsi_target_auth_tag').distinct()]

    def clean_iscsi_target_authgroup(self):
        value = self.cleaned_data.get('iscsi_target_authgroup')
        return None if value and int(value) == -1 else value

    def middleware_clean(self, data):
        targetobj = self.cleaned_data.get('iscsi_target')
        with client as c:
            target = c.call('iscsi.target.query', [('id', '=', targetobj.id)], {'get': True})

        data['auth'] = data.pop('authgroup') or None
        data['authmethod'] = AUTHMETHOD_LEGACY_MAP.get(data.pop('authtype'))
        data['initiator'] = data.pop('initiatorgroup')
        data['portal'] = data.pop('portalgroup')

        if self.instance.id:
            orig = models.iSCSITargetGroups.objects.get(pk=self.instance.id).__dict__
            old = {
                'authmethod': AUTHMETHOD_LEGACY_MAP.get(orig['iscsi_target_authtype']),
                'portal': orig['iscsi_target_portalgroup_id'],
                'initiator': orig['iscsi_target_initiatorgroup_id'],
                'auth': orig['iscsi_target_authgroup'],
            }
            for idx, i in enumerate(target['groups']):
                if (
                    i['portal'] == old['portal'] and i['initiator'] == old['initiator'] and
                    i['auth'] == old['auth'] and i['authmethod'] == old['authmethod']
                ):
                    break
            else:
                raise forms.ValidationError('Target group not found')
            target['groups'][idx] = data
        else:
            target['groups'].append(data)
        self.instance.id = targetobj.id
        target.pop('id')
        return target


class TargetExtentDelete(Form):
    '''
    Delete form for Targets/Associated Targets
    '''
    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super(TargetExtentDelete, self).__init__(*args, **kwargs)
        if not self.data:
            connected_targets = notifier().iscsi_connected_targets()
            target_to_be_deleted = None
            if isinstance(self.instance, models.iSCSITarget):
                target_to_be_deleted = self.instance.iscsi_target_name
            elif isinstance(self.instance, models.iSCSITargetToExtent):
                target_to_be_deleted = self.instance.iscsi_target.iscsi_target_name

            if not target_to_be_deleted.startswith(('iqn.', 'naa.', 'eui.')):
                basename = models.iSCSITargetGlobalConfiguration.objects.order_by('-id')[0].iscsi_basename
                target_to_be_deleted = basename + ':' + target_to_be_deleted

            if target_to_be_deleted in connected_targets:
                self.errors['__all__'] = self.error_class(
                    ["Warning: Target is in use"])


class ExtentDelete(Form):
    delete = forms.BooleanField(
        label=_("Delete underlying file"),
        initial=False,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super(ExtentDelete, self).__init__(*args, **kwargs)
        if self.instance.iscsi_target_extent_type != 'File':
            self.fields.pop('delete')
        if not self.data:
            targets_in_use = notifier().iscsi_connected_targets()
            is_extent_active = False
            target_to_extent_list = models.iSCSITargetToExtent.objects.filter(
                iscsi_extent__iscsi_target_extent_name=self.instance.iscsi_target_extent_name)
            basename = models.iSCSITargetGlobalConfiguration.objects.order_by('-id')[0].iscsi_basename
            for target_to_extent in target_to_extent_list:
                target = target_to_extent.iscsi_target.iscsi_target_name
                if not target.startswith(('iqn.', 'naa.', 'eui.')):
                    target = basename + ':' + target
                if target in targets_in_use:
                    is_extent_active = True
                    # Extent is active. No need to check other targets.
                    break
            if is_extent_active:
                self.errors['__all__'] = self.error_class(
                    ["Warning: Associated Target is in use"])

    def done(self, *args, **kwargs):
        if (
            self.instance.iscsi_target_extent_type == 'File' and
            self.cleaned_data['delete'] and
            os.path.exists(self.instance.iscsi_target_extent_path)
        ):
            data = {}
            data['type'] = self.instance.iscsi_target_extent_type
            data['path'] = self.instance.iscsi_target_extent_path

            with client as c:
                c.call('iscsi.extent.remove_extent_file', data)


class SMARTForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "smart_"
    middleware_attr_schema = "smart"
    middleware_plugin = "smart"
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.SMART

    def __init__(self, *args, **kwargs):
        if "instance" in kwargs:
            kwargs.setdefault("initial", {})
            kwargs["initial"]["smart_email"] = " ".join(kwargs["instance"].smart_email.split(","))

        super(SMARTForm, self).__init__(*args, **kwargs)

    def middleware_clean(self, update):
        update["powermode"] = update["powermode"].upper()
        update["email"] = update["email"].split()
        return update


class DomainControllerForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "dc_"
    middleware_attr_schema = "domaincontroller"
    middleware_exclude_fields = ['passwd2']
    middleware_plugin = "domaincontroller"
    is_singletone = True

    dc_passwd2 = forms.CharField(
        max_length=50,
        label=_("Confirm Administrator Password"),
        widget=forms.widgets.PasswordInput(),
        required=False,
    )

    class Meta:
        fields = [
            'dc_realm',
            'dc_domain',
            'dc_role',
            'dc_dns_forwarder',
            'dc_forest_level',
            'dc_passwd',
            'dc_passwd2',
            'dc_kerberos_realm'
        ]
        model = models.DomainController
        widgets = {
            'dc_passwd': forms.widgets.PasswordInput(render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super(DomainControllerForm, self).__init__(*args, **kwargs)
        if self.instance.dc_passwd:
            self.fields['dc_passwd'].required = False
        if self._api is True:
            del self.fields['dc_passwd2']

    def clean_dc_passwd2(self):
        password1 = self.cleaned_data.get("dc_passwd")
        password2 = self.cleaned_data.get("dc_passwd2")
        if password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("dc_passwd"):
            cdata['dc_passwd'] = self.instance.dc_passwd
        return cdata

    def middleware_clean(self, data):
        data['role'] = data['role'].upper()
        return data


class WebDAVForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = 'webdav_'
    middleware_attr_schema = 'webdav'
    middleware_exclude_fields = ['password2']
    middleware_plugin = 'webdav'
    is_singletone = True

    webdav_password2 = forms.CharField(
        max_length=120,
        label=_("Confirm WebDAV Password"),
        widget=forms.widgets.PasswordInput(),
        required=False,
    )

    class Meta:
        fields = (
            'webdav_protocol', 'webdav_tcpport', 'webdav_tcpportssl',
            'webdav_certssl', 'webdav_htauth', 'webdav_password'
        )
        model = models.WebDAV
        widgets = {
            'webdav_tcpport': forms.widgets.TextInput(),
            'webdav_tcpportssl': forms.widgets.TextInput(),
            'webdav_password': forms.widgets.PasswordInput(),
        }

    def __init__(self, *args, **kwargs):
        super(WebDAVForm, self).__init__(*args, **kwargs)
        if self.instance.webdav_password:
            self.fields['webdav_password'].required = False
            self.fields['webdav_password2'].required = False
        if self._api is True:
            del self.fields['webdav_password2']
        self.fields['webdav_protocol'].widget.attrs['onChange'] = (
            "webdavprotocolToggle();"
        )
        self.fields['webdav_htauth'].widget.attrs['onChange'] = (
            "webdavhtauthToggle();"
        )

    def clean(self):
        cdata = self.cleaned_data

        if self._api is not True and cdata.get("webdav_password") != cdata.get("webdav_password2"):
            self._errors["webdav_password"] = self.error_class(
                [_("The two password fields didn't match.")]
            )
        elif not cdata.get("webdav_password"):
            cdata['webdav_password'] = self.instance.webdav_password
        if not cdata.get("webdav_tcpport"):
            cdata['webdav_tcpport'] = self.instance.webdav_tcpport
        if not cdata.get("webdav_tcpportssl"):
            cdata['webdav_tcpportssl'] = self.instance.webdav_tcpportssl

        return cdata

    def middleware_clean(self, data):
        data['protocol'] = data['protocol'].upper()
        data['htauth'] = data['htauth'].upper()

        return data


class S3Form(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "s3_"
    middleware_attr_schema = "s3"
    middleware_exclude_fields = ('secret_key2', )
    middleware_plugin = "s3"
    is_singletone = True

    s3_bindip = forms.ChoiceField(
        label=models.S3._meta.get_field("s3_bindip").verbose_name,
        help_text=models.S3._meta.get_field("s3_bindip").help_text,
        widget=forms.widgets.FilteringSelect(),
        required=False,
        choices=(),
    )
    s3_secret_key2 = forms.CharField(
        max_length=128,
        label=_("Confirm S3 Key"),
        widget=forms.widgets.PasswordInput(render_value=True),
        required=False,
    )

    class Meta:
        fields = '__all__'
        widgets = {
            's3_secret_key': forms.widgets.PasswordInput(render_value=True),
            's3_bindport': forms.widgets.TextInput(),
        }
        model = models.S3

    def __init__(self, *args, **kwargs):
        super(S3Form, self).__init__(*args, **kwargs)
        key_order(self, 1, 's3_bindip', instance=True)
        key_order(self, 2, 's3_bindport', instance=True)
        key_order(self, 3, 's3_access_key', instance=True)
        key_order(self, 4, 's3_secret_key', instance=True)
        key_order(self, 5, 's3_secret_key2', instance=True)
        key_order(self, 6, 's3_disks', instance=True)
        key_order(self, 7, 's3_certificate', instance=True)
        key_order(self, 8, 's3_mode', instance=True)
        key_order(self, 9, 's3_browser', instance=True)

        self.fields['s3_bindip'].choices = [('0.0.0.0', '0.0.0.0')] + list(choices.IPChoices())
        if self.instance.id and self.instance.s3_bindip:
            bindips = []
            for ip in self.instance.s3_bindip:
                bindips.append(ip.encode('utf-8'))

            self.fields['s3_bindip'].initial = (bindips)
        else:
            self.fields['s3_bindip'].initial = ('')

        if self.instance.id:
            self.fields['s3_secret_key2'].initial = self.instance.s3_secret_key
        if self._api is True:
            del self.fields['s3_secret_key2']

        self.fields['s3_mode'].widget = forms.widgets.HiddenInput()

    def clean_s3_secret_key2(self):
        s3_secret_key1 = self.cleaned_data.get("s3_secret_key")
        s3_secret_key2 = self.cleaned_data.get("s3_secret_key2")
        if s3_secret_key1 != s3_secret_key2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return s3_secret_key2

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("s3_secret_key"):
            cdata["s3_secret_key"] = self.instance.s3_secret_key
        return cdata

    def middleware_clean(self, data):
        if 'disks' in data:
            data['storage_path'] = data.pop('disks')
        data.pop('mode', None)
        return data


class AsigraForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.Asigra
        exclude = ['asigra_bindip']

    def __init__(self, *args, **kwargs):
        super(AsigraForm, self).__init__(*args, **kwargs)

        self.fields['filesystem'] = forms.ChoiceField(
            label=self.fields['filesystem'].label,
        )
        volnames = [o.vol_name for o in Volume.objects.all()]
        choices = set([
			y for y in list(notifier().list_zfs_fsvols().items())
            if '/' in y[0] and y[0].split('/')[0] in volnames
        ])
        self.fields['filesystem'].choices = choices

        # XXX
        # At some point, we want to be able to change a path of necessary. This,
        # coupled with the save() method accomplish that, but the asigra
        # database needs to be updated for this to work. Keeping this in
        # for now until we get the go ahead to do this from asigra.
        # XXX

        self._orig_filesystem = self.instance.filesystem
        if self.instance.id and self.instance.filesystem:
            if self.instance.filesystem:
                self.fields["filesystem"].widget.attrs["readonly"] = True

    def clean_filesystem(self):
        fs = self.cleaned_data.get("filesystem")
        if not fs:
            raise forms.ValidationError("Filesystem can't be empty!")
        if not os.path.exists(f'/mnt/{fs}'):
            raise forms.ValidationError("Filesystem does not exist!")
        return fs

    def save(self):
        obj = super(AsigraForm, self).save()
        if self._orig_filesystem != obj.filesystem:
            notifier().restart("asigra")
        return obj
