# Copyright 2014 iXsystems, Inc.
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
import base64
import logging
import os
import tempfile

from django.forms import FileField
from django.utils.translation import ugettext_lazy as _

from dojango import forms

from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.directoryservice import models
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.form import MiddlewareModelForm

log = logging.getLogger('directoryservice.form')


class idmap_ad_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_ad
        exclude = [
            'idmap_ad_domain',
        ]


class idmap_autorid_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_autorid
        exclude = [
            'idmap_autorid_domain',
        ]


class idmap_fruit_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_fruit
        exclude = [
            'idmap_fruit_domain',
        ]


class idmap_ldap_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_ldap
        exclude = [
            'idmap_ldap_domain',
        ]


class idmap_nss_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_nss
        exclude = [
            'idmap_nss_domain',
        ]


class idmap_rfc2307_Form(ModelForm):
    idmap_rfc2307_ldap_user_dn_password2 = forms.CharField(
        max_length=120,
        label=_("Confirm LDAP User DN Password"),
        widget=forms.widgets.PasswordInput(),
        required=False
    )

    class Meta:
        fields = [
            'idmap_rfc2307_range_low',
            'idmap_rfc2307_range_high',
            'idmap_rfc2307_ldap_server',
            'idmap_rfc2307_bind_path_user',
            'idmap_rfc2307_bind_path_group',
            'idmap_rfc2307_user_cn',
            'idmap_rfc2307_cn_realm',
            'idmap_rfc2307_ldap_domain',
            'idmap_rfc2307_ldap_url',
            'idmap_rfc2307_ldap_user_dn',
            'idmap_rfc2307_ldap_user_dn_password',
            'idmap_rfc2307_ldap_user_dn_password2',
            'idmap_rfc2307_ldap_realm',
            'idmap_rfc2307_ssl',
            'idmap_rfc2307_certificate'
        ]
        model = models.idmap_rfc2307
        widgets = {
            'idmap_rfc2307_ldap_user_dn_password':
                forms.widgets.PasswordInput(render_value=False)
        }
        exclude = [
            'idmap_rfc2307_domain',
        ]

    def __init__(self, *args, **kwargs):
        super(idmap_rfc2307_Form, self).__init__(*args, **kwargs)
        if self.instance.idmap_rfc2307_ldap_user_dn_password:
            self.fields['idmap_rfc2307_ldap_user_dn_password'].required = False
        if self._api is True:
            del self.fields['idmap_rfc2307_ldap_user_dn_password']

    def clean_idmap_rfc2307_ldap_user_dn_password2(self):
        password1 = self.cleaned_data.get("idmap_rfc2307_ldap_user_dn_password")
        password2 = self.cleaned_data.get("idmap_rfc2307_ldap_user_dn_password2")
        if password1 != password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return password2

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("idmap_rfc2307_ldap_user_dn_password"):
            cdata['idmap_rfc2307_ldap_user_dn_password'] = \
                self.instance.idmap_rfc2307_ldap_user_dn_password
        return cdata


class idmap_rid_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_rid
        exclude = [
            'idmap_rid_domain'
        ]


class idmap_tdb_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_tdb
        exclude = [
            'idmap_tdb_domain',
        ]


class idmap_script_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_script
        exclude = [
            'idmap_script_domain',
        ]


class ActiveDirectoryForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = 'ad_'
    middleware_attr_schema = 'ad'
    middleware_plugin = 'activedirectory'
    is_singletone = True

    ad_netbiosname = forms.CharField(
        max_length=120,
        label=_("NetBIOS name"),
    )
    ad_netbiosname_b = forms.CharField(
        max_length=120,
        label=_("NetBIOS name"),
    )
    ad_netbiosalias = forms.CharField(
        max_length=120,
        label=_("NetBIOS alias"),
        required=False,
    )
    ad_kerberos_principal = forms.ChoiceField(
        label=models.ActiveDirectory._meta.get_field('ad_kerberos_principal').verbose_name,
        required=False,
        choices=choices.KERBEROS_PRINCIPAL_CHOICES(),
        help_text=_(
            "Kerberos principal to use for AD-related UI and middleware operations. "
            "Populated with exiting  principals from the system keytab. "
            "A keytab entry is generated for the the Active Directory Machine Account "
            "The account name for the server is the server netbios name appended with a '$' "
            "Bind credentails are automatically cleared after the has is joined to Active "
            "Directory. Later operations are perfomed by the AD machine account, which has "
            "restricted privileges in the AD domain."),
        initial=''
    )

    advanced_fields = [
        'ad_netbiosname',
        'ad_netbiosname_b',
        'ad_netbiosalias',
        'ad_ssl',
        'ad_certificate',
        'ad_verbose_logging',
        'ad_unix_extensions',
        'ad_allow_trusted_doms',
        'ad_use_default_domain',
        'ad_createcomputer',
        'ad_allow_dns_updates',
        'ad_disable_freenas_cache',
        'ad_site',
        'ad_kerberos_realm',
        'ad_kerberos_principal',
        'ad_nss_info',
        'ad_timeout',
        'ad_dns_timeout',
        'ad_idmap_backend',
        'ad_ldap_sasl_wrapping'
    ]

    class Meta:
        fields = '__all__'
        exclude = ['ad_idmap_backend_type', 'ad_userdn', 'ad_groupdn']

        model = models.ActiveDirectory
        widgets = {
            'ad_bindpw': forms.widgets.PasswordInput(render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super(ActiveDirectoryForm, self).__init__(*args, **kwargs)
        with client as c:
            ad = c.call('activedirectory.config')

            self.fields['ad_netbiosname'].initial = ad['netbiosname']
            if 'netbiosname_b' in ad:
                self.fields['ad_netbiosname_b'].initial = ad['netbiosname_b']
            else:
                del self.fields['ad_netbiosname_b']

    def save(self):
        try:
            super(ActiveDirectoryForm, self).save()
        except Exception as e:
            raise MiddlewareError(e)

    def middleware_clean(self, data):
        for key in ['certificate', 'nss_info']:
            if not data[key]:
                data.pop(key)

        data['netbiosalias'] = data['netbiosalias'].split()
        if data['kerberos_principal'] == '---------':
            data['kerberos_principal'] = ''

        if data['kerberos_realm']:
            data['kerberos_realm'] = {'id': data['kerberos_realm']}
        else:
            data.pop('kerberos_realm')

        return data


class NISForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'nis_'
    middleware_attr_schema = 'nis'
    middleware_plugin = 'nis'
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.NIS

    def __init__(self, *args, **kwargs):
        super(NISForm, self).__init__(*args, **kwargs)
        self.fields["nis_enable"].widget.attrs["onChange"] = (
            "nis_mutex_toggle();"
        )

    def middleware_clean(self, data):
        data['servers'] = data['servers'].split(',')
        return data


class LDAPForm(MiddlewareModelForm, ModelForm):
    middleware_attr_prefix = 'ldap_'
    middleware_attr_schema = 'ldap'
    middleware_plugin = 'ldap'
    is_singletone = True

    ldap_kerberos_principal = forms.ChoiceField(
        label=models.LDAP._meta.get_field('ldap_kerberos_principal').verbose_name,
        required=False,
        choices=choices.KERBEROS_PRINCIPAL_CHOICES(),
        help_text=_("Kerberos principal to use for LDAP-related operations."),
        initial=''
    )

    advanced_fields = [
        'ldap_anonbind',
        'ldap_usersuffix',
        'ldap_groupsuffix',
        'ldap_passwordsuffix',
        'ldap_machinesuffix',
        'ldap_sudosuffix',
        'ldap_netbiosname_a',
        'ldap_netbiosname_b',
        'ldap_netbiosalias',
        'ldap_kerberos_realm',
        'ldap_kerberos_principal',
        'ldap_ssl',
        'ldap_certificate',
        'ldap_timeout',
        'ldap_dns_timeout',
        'ldap_idmap_backend',
        'ldap_has_samba_schema',
        'ldap_auxiliary_parameters',
        'ldap_schema'
    ]

    class Meta:
        fields = '__all__'
        exclude = ['ldap_idmap_backend_type']

        model = models.LDAP
        widgets = {
            'ldap_bindpw': forms.widgets.PasswordInput(render_value=False),
        }

    def __init__(self, *args, **kwargs):
        super(LDAPForm, self).__init__(*args, **kwargs)

    def save(self):
        try:
            super(LDAPForm, self).save()
        except Exception as e:
            raise MiddlewareError(e)

    def middleware_clean(self, data):
        for key in ['certificate']:
            if not data[key]:
                data.pop(key)

        if data['kerberos_principal'] == '---------':
            data['kerberos_principal'] = ''

        data['hostname'] = data['hostname'].split()

        if data['kerberos_realm']:
            data['kerberos_realm'] = {'id': data['kerberos_realm']}
        else:
            data.pop('kerberos_realm')

        return data


class KerberosRealmForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'krb_'
    middleware_attr_schema = 'kerberos_realm'
    middleware_plugin = 'kerberos.realm'
    is_singletone = False

    class Meta:
        fields = '__all__'
        model = models.KerberosRealm

    def __init__(self, *args, **kwargs):
        super(KerberosRealmForm, self).__init__(*args, **kwargs)

    def middleware_clean(self, data):
        for i in ['kdc', 'admin_server', 'kpasswd_server']:
            data[i] = data[i].split()
        return data


class KerberosKeytabCreateForm(ModelForm):
    freeadmin_form = True

    keytab_file = FileField(
        label=_("Kerberos Keytab"),
        required=False
    )

    class Meta:
        fields = '__all__'
        model = models.KerberosKeytab

    def clean_keytab_file(self):
        keytab_file = self.cleaned_data.get("keytab_file", None)
        if not keytab_file:
            raise forms.ValidationError(
                _("A keytab is required.")
            )

        if isinstance(keytab_file, str):
            encoded = keytab_file
        else:
            if hasattr(keytab_file, 'temporary_file_path'):
                filename = keytab_file.temporary_file_path()
                with open(filename, "rb") as f:
                    keytab_contents = f.read()
                    encoded = base64.b64encode(keytab_contents).decode()
            else:
                filename = tempfile.mktemp(dir='/tmp')
                with open(filename, 'wb+') as f:
                    for c in keytab_file.chunks():
                        f.write(c)
                with open(filename, "rb") as f:
                    keytab_contents = f.read()
                    encoded = base64.b64encode(keytab_contents).decode()
                os.unlink(filename)

        return encoded

    def save(self):
        super(KerberosKeytabCreateForm, self).save()
        with client as c:
            c.call('kerberos.start')


class KerberosKeytabEditForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'keytab_'
    middleware_attr_schema = 'kerberos_keytab'
    middleware_plugin = 'kerberos.keytab'
    is_singletone = True

    class Meta:
        fields = '__all__'
        exclude = ['keytab_file']
        model = models.KerberosKeytab

    def __init__(self, *args, **kwargs):
        super(KerberosKeytabEditForm, self).__init__(*args, **kwargs)

        self.fields['keytab_name'].widget.attrs['readonly'] = True
        self.fields['keytab_name'].widget.attrs['class'] = (
            'dijitDisabled dijitTextBoxDisabled dijitValidationTextBoxDisabled'
        )


class KerberosSettingsForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'ks_'
    middleware_attr_schema = 'kerberos_settings'
    middleware_plugin = 'kerberos'
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.KerberosSettings
