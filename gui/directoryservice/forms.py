#+
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
import re
import shutil
import tempfile

from django.forms import FileField
from django.utils.translation import ugettext_lazy as _

from dojango import forms

from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FreeNAS_LDAP,
    FreeNAS_ActiveDirectory_Exception,
)
from freenasUI.common.ssl import get_certificateauthority_path
from freenasUI.common.system import (
    validate_netbios_name,
    validate_netbios_names,
    compare_netbios_names
)
from freenasUI.directoryservice import models, utils
from freenasUI.middleware.notifier import notifier
from freenasUI.services.exceptions import ServiceFailed

log = logging.getLogger('directoryservice.form')


class idmap_ad_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_ad
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_adex_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_adex
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_autorid_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_autorid
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_hash_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_hash
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_ldap_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_ldap
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_nss_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_nss
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_rfc2307_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_rfc2307
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_rid_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_rid
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_tdb_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_tdb
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class idmap_tdb2_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_tdb2
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class NT4Form(ModelForm):
    nt4_adminpw2 = forms.CharField(
        max_length=50,
        label=_("Confirm Administrator Password"),
        widget=forms.widgets.PasswordInput(),
        required=False,
    )

    advanced_fields = [
        'nt4_use_default_domain',
        'nt4_idmap_backend'
    ]

    class Meta:
        model = models.NT4
        widgets = {
            'nt4_adminpw': forms.widgets.PasswordInput(render_value=False),
        }
        fields = [
            'nt4_dcname',
            'nt4_netbiosname',
            'nt4_workgroup',
            'nt4_adminname',
            'nt4_adminpw',
            'nt4_adminpw2',
            'nt4_use_default_domain',
            'nt4_idmap_backend',
            'nt4_enable'
        ]

    def __init__(self, *args, **kwargs):
        super(NT4Form, self).__init__(*args, **kwargs)
        if self.instance.nt4_adminpw:
            self.fields['nt4_adminpw'].required = False
        if self._api is True:
            del self.fields['nt4_adminpw2']

        self.instance._original_nt4_idmap_backend = \
            self.instance.nt4_idmap_backend

        self.fields["nt4_enable"].widget.attrs["onChange"] = (
            "nt4_mutex_toggle();"
        )

    def clean_nt4_adminpw2(self):
        password1 = self.cleaned_data.get("nt4_adminpw")
        password2 = self.cleaned_data.get("nt4_adminpw2")
        if password1 != password2:
            raise forms.ValidationError(
                _("The two password fields didn't match.")
            )
        return password2

    def clean_nt4_idmap_backend(self):
        nt4_idmap_backend = self.cleaned_data.get("nt4_idmap_backend")
        if not nt4_idmap_backend:
            nt4_idmap_backend = None
        return nt4_idmap_backend

    def clean_nt4_netbiosname(self):
        netbiosname = self.cleaned_data.get("nt4_netbiosname")
        try:
            validate_netbios_names(netbiosname)
        except Exception as e:
            raise forms.ValidationError(_("netbiosname: %s" % e))
        return netbiosname

    def clean_nt4_workgroup(self):
        workgroup = self.cleaned_data.get("nt4_workgroup")
        try:
            validate_netbios_name(workgroup)
        except Exception as e:
            raise forms.ValidationError(_("workgroup: %s" % e))
        return workgroup

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("nt4_adminpw"):
            cdata['nt4_adminpw'] = self.instance.nt4_adminpw
        return cdata

    def save(self):
        enable = self.cleaned_data.get("nt4_enable")
        started = notifier().started("nt4")
        if enable:
            if started is True:
                started = notifier().restart("nt4")
            if started is False:
                started = notifier().start("nt4")
            if started is False:
                self.instance.ad_enable = False
                super(NT4Form, self).save()
                raise ServiceFailed("nt4",
                    _("NT4 failed to reload."))
        else:
            if started == True:
                started = notifier().stop("nt4")

        obj = super(NT4Form, self).save()
        return obj


class ActiveDirectoryForm(ModelForm):

    advanced_fields = [
        'ad_netbiosname',
        'ad_ssl',
        'ad_certificate',
        'ad_verbose_logging',
        'ad_unix_extensions',
        'ad_allow_trusted_doms',
        'ad_use_default_domain',
        'ad_site',
        'ad_dcname',
        'ad_gcname',
        'ad_kerberos_realm',
        'ad_kerberos_keytab',
        'ad_nss_info',
        'ad_timeout',
        'ad_dns_timeout',
        'ad_idmap_backend',
        'ad_ldap_sasl_wrapping'
    ]

    class Meta:
        fields = '__all__'
        exclude = ['ad_idmap_backend_type']
        model = models.ActiveDirectory
        widgets = {
            'ad_bindpw': forms.widgets.PasswordInput(render_value=False),
        }

    def __original_save(self):
        for name in (
            'ad_domainname',
            'ad_netbiosname',
            'ad_allow_trusted_doms',
            'ad_use_default_domain',
            'ad_unix_extensions',
            'ad_verbose_logging',
            'ad_bindname',
            'ad_bindpw'
        ):
            setattr(
                self.instance,
                "_original_%s" % name,
                getattr(self.instance, name)
            )

    def __original_changed(self):
        if self.instance._original_ad_domainname != self.instance.ad_domainname:
            return True
        if self.instance._original_ad_netbiosname != self.instance.ad_netbiosname:
            return True
        if self.instance._original_ad_allow_trusted_doms != self.instance.ad_allow_trusted_doms:
            return True
        if self.instance._original_ad_use_default_domain != self.instance.ad_use_default_domain:
            return True
        if self.instance._original_ad_unix_extensions != self.instance.ad_unix_extensions:
            return True
        if self.instance._original_ad_verbose_logging != self.instance.ad_verbose_logging:
            return True
        if self.instance._original_ad_bindname != self.instance.ad_bindname:
            return True
        if self.instance._original_ad_bindpw != self.instance.ad_bindpw:
            return True
        return False

    def __init__(self, *args, **kwargs):
        super(ActiveDirectoryForm, self).__init__(*args, **kwargs)
        if self.instance.ad_bindpw:
            self.fields['ad_bindpw'].required = False
        self.__original_save()

        self.fields["ad_idmap_backend"].widget.attrs["onChange"] = (
            "activedirectory_idmap_check();"
        )

        self.fields["ad_enable"].widget.attrs["onChange"] = (
            "activedirectory_mutex_toggle();"
        )

    def clean_ad_dcname(self):
        ad_dcname = self.cleaned_data.get('ad_dcname')
        ad_dcport = 389 

        ad_ssl = self.cleaned_data.get('ad_ssl')
        if ad_ssl == 'on':
            ad_dcport = 636

        if not ad_dcname:
            return None

        parts = ad_dcname.split(':')
        ad_dcname = parts[0]
        if len(parts) > 1 and parts[1].isdigit():
            ad_dcport = long(parts[1])

        errors = []
        try:
            ret = FreeNAS_ActiveDirectory.port_is_listening(
                host=ad_dcname, port=ad_dcport, errors=errors
            )
     
            if ret is False:
                raise Exception(
                    'Invalid Host/Port: %s' % errors[0]
                )

        except Exception as e:
            raise forms.ValidationError('%s.' % e)

        return self.cleaned_data.get('ad_dcname')
    
    def clean_ad_gcname(self):
        ad_gcname = self.cleaned_data.get('ad_gcname')
        ad_gcport = 3268

        ad_ssl = self.cleaned_data.get('ad_ssl')
        if ad_ssl == 'on':
            ad_gcport = 3269

        if not ad_gcname:
            return None

        parts = ad_gcname.split(':')
        ad_gcname = parts[0]
        if len(parts) > 1 and parts[1].isdigit():
            ad_gcport = long(parts[1])

        errors = []
        try:
            ret = FreeNAS_ActiveDirectory.port_is_listening(
                host=ad_gcname, port=ad_gcport, errors=errors
            )
     
            if ret is False:
                raise Exception(
                    'Invalid Host/Port: %s' % errors[0]
                )

        except Exception as e:
            raise forms.ValidationError('%s.' % e)

        return self.cleaned_data.get('ad_gcname')

    def clean_ad_netbiosname(self):
        netbiosname = self.cleaned_data.get("ad_netbiosname")
        try:
            validate_netbios_names(netbiosname)
        except Exception as e:
            raise forms.ValidationError(e)
        return netbiosname

    def clean(self):
        cdata = self.cleaned_data
        domain = cdata.get("ad_domainname")
        bindname = cdata.get("ad_bindname")
        bindpw = cdata.get("ad_bindpw")
        site = cdata.get("ad_site")
        netbiosname = cdata.get("ad_netbiosname")
        ssl = cdata.get("ad_ssl")
        certificate = cdata["ad_certificate"]
        ad_kerberos_keytab = cdata["ad_kerberos_keytab"]
        workgroup = None

        if certificate: 
            certificate = certificate.get_certificate_path()

        args = {
            'domain': domain,
            'site': site,
            'ssl': ssl,
            'certfile': certificate
        }

        if not ad_kerberos_keytab:
            if not cdata.get("ad_bindpw"):
                cdata['ad_bindpw'] = self.instance.ad_bindpw

            if not bindname:
                raise forms.ValidationError("No domain account name specified") 
            if not bindpw:
                raise forms.ValidationError("No domain account password specified") 

            binddn = "%s@%s" % (bindname, domain)
            errors = []

            try:
                ret = FreeNAS_ActiveDirectory.validate_credentials(
                    domain, site=site, ssl=ssl, certfile=certificate,
                    binddn=binddn, bindpw=bindpw, errors=errors
                )
                if ret is False:
                    raise forms.ValidationError("%s." % errors[0])
            except FreeNAS_ActiveDirectory_Exception, e:
                raise forms.ValidationError('%s.' % e)

            args['binddn'] = binddn
            args['bindpw'] = bindpw

        else: 
            args['keytab_name'] = ad_kerberos_keytab.keytab_name
            args['keytab_principal'] = ad_kerberos_keytab.keytab_principal
            args['keytab_file'] = '/etc/krb5.keytab'

        workgroup = FreeNAS_ActiveDirectory.get_workgroup_name(**args)
        if workgroup:
            if compare_netbios_names(netbiosname, workgroup, None):
                raise forms.ValidationError("The NetBIOS name cannot be the same as the workgroup name!")

        else: 
            log.warn("Unable to determine workgroup name")

        if ssl in ("off", None):
            return cdata

        if not certificate:
            raise forms.ValidationError(
                "SSL/TLS specified without certificate")

        return cdata

    def save(self):
        enable = self.cleaned_data.get("ad_enable")
        if self.__original_changed():
            notifier()._clear_activedirectory_config()

        started = notifier().started("activedirectory")
        obj = super(ActiveDirectoryForm, self).save()

        if enable:
            if started is True:
                started = notifier().restart("activedirectory")
            if started is False:
                started = notifier().start("activedirectory")
            if started is False:
                self.instance.ad_enable = False
                super(ActiveDirectoryForm, self).save()
                raise ServiceFailed("activedirectory",
                    _("Active Directory failed to reload."))
        else:
            if started == True:
                started = notifier().stop("activedirectory")
        return obj


class NISForm(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.NIS

    def __init__(self, *args, **kwargs):
        super(NISForm, self).__init__(*args, **kwargs)
        self.fields["nis_enable"].widget.attrs["onChange"] = (
            "nis_mutex_toggle();"
        )

    def save(self):
        enable = self.cleaned_data.get("nis_enable")

        started = notifier().started("nis")
        super(NISForm, self).save()

        if enable:
            if started is True:
                started = notifier().restart("nis")
            if started is False:
                started = notifier().start("nis")
            if started is False:
                self.instance.ad_enable = False
                super(NISForm, self).save()
                raise ServiceFailed("nis", _("NIS failed to reload."))
        else:
            if started == True:
                started = notifier().stop("nis")


class LDAPForm(ModelForm):

    advanced_fields = [
        'ldap_anonbind',
        'ldap_usersuffix',
        'ldap_groupsuffix',
        'ldap_passwordsuffix',
        'ldap_machinesuffix',
        'ldap_sudosuffix',
        'ldap_kerberos_realm',
        'ldap_kerberos_keytab',
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
        exclude = [
            'ldap_idmap_backend_type'
        ]
        model = models.LDAP
        widgets = {
            'ldap_bindpw': forms.widgets.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super(LDAPForm, self).__init__(*args, **kwargs)
        self.fields["ldap_enable"].widget.attrs["onChange"] = (
            "ldap_mutex_toggle();"
        )

    def clean_bindpw(self):
        cdata = self.cleaned_data
        if not cdata.get("ldap_bindpw"):
            cdata["ldap_bindpw"] = self.instance.ldap_bindpw

        binddn = cdata.get("ldap_binddn")
        bindpw = cdata.get("ldap_bindpw")
        basedn = cdata.get("ldap_basedn")
        hostname = cdata.get("ldap_hostname")
        errors = []

        certfile = None
        ssl = cdata.get("ldap_ssl")
        if ssl in ('start_tls', 'on'):
            certificate = cdata["ldap_certificate"]
            certfile = get_certificateauthority_path(certificate)

        ret = FreeNAS_LDAP.validate_credentials(
            hostname, binddn=binddn, bindpw=bindpw, basedn=basedn,
            certfile=certfile, ssl=ssl, errors=errors
        )
        if ret is False:
            raise forms.ValidationError("%s." % errors[0])

    def check_for_samba_schema(self):
        self.clean_bindpw()

        cdata = self.cleaned_data
        binddn = cdata.get("ldap_binddn")
        bindpw = cdata.get("ldap_bindpw")
        basedn = cdata.get("ldap_basedn")
        hostname = cdata.get("ldap_hostname")

        certfile = None
        ssl = cdata.get("ldap_ssl")
        if ssl in ('start_tls', 'on'):
            certificate = cdata["ldap_certificate"]
            certfile = get_certificateauthority_path(certificate)

        fl = FreeNAS_LDAP(
            host=hostname,
            binddn=binddn,
            bindpw=bindpw,
            basedn=basedn,
            certfile=certfile,
            ssl=ssl
        )

        if fl.has_samba_schema():
            self.instance.ldap_has_samba_schema = True
        else:
            self.instance.ldap_has_samba_schema = False

    def clean(self):
        cdata = self.cleaned_data
        ssl = cdata.get("ldap_ssl")
        if ssl in ("off", None):
            #self.check_for_samba_schema()
            return cdata

        certificate = cdata["ldap_certificate"]
        if not certificate:
            raise forms.ValidationError(
                "SSL/TLS specified without certificate")

        #self.check_for_samba_schema()
        return cdata

    def save(self):
        enable = self.cleaned_data.get("ldap_enable")

        started = notifier().started("ldap")
        obj = super(LDAPForm, self).save()

        if enable:
            if started is True:
                started = notifier().restart("ldap")
            if started is False:
                started = notifier().start("ldap")
            if started is False:
                self.instance.ldap_enable = False
                super(LDAPForm, self).save()
                raise ServiceFailed("ldap",
                    _("LDAP failed to reload."))
        else:
            if started == True:
                started = notifier().stop("ldap")

        return obj

    def done(self, request, events):
        events.append("refreshById('tab_LDAP')")
        super(LDAPForm, self).done(request, events)


class KerberosRealmForm(ModelForm):
    advanced_fields = [
        'krb_admin_server',
        'krb_kpasswd_server'
    ]

    class Meta:
        fields = '__all__'
        model = models.KerberosRealm

    def clean_krb_realm(self):
        krb_realm = self.cleaned_data.get("krb_realm", None)
        if krb_realm:
            krb_realm = krb_realm.upper()
        return krb_realm

    def save(self):
        super(KerberosRealmForm, self).save()
        notifier().start("ix-kerberos")


class KerberosKeytabCreateForm(ModelForm):
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

        encoded = None
        if hasattr(keytab_file, 'temporary_file_path'):
            filename = keytab_file.temporary_file_path()
            with open(temporary_file_path, "r") as f:
                keytab_contents = f.read()
                encoded = base64.b64encode(keytab_contents)
                f.close()
        else:
            filename = tempfile.mktemp(dir='/tmp')
            with open(filename, 'wb+') as f:
                for c in keytab_file.chunks():
                    f.write(c)
                f.close()
            with open(filename, "r") as f:
                keytab_contents = f.read()
                encoded = base64.b64encode(keytab_contents)
                f.close()
            os.unlink(filename)

        return encoded

    def save(self):
        super(KerberosKeytabCreateForm, self).save()
        notifier().start("ix-kerberos")


class KerberosKeytabEditForm(ModelForm):

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
        self.fields['keytab_principal'].widget.attrs['readonly'] = True
        self.fields['keytab_principal'].widget.attrs['class'] = (
            'dijitDisabled dijitTextBoxDisabled dijitValidationTextBoxDisabled'
        )

    def save(self):
        super(KerberosKeytabEditForm, self).save()
        notifier().start("ix-kerberos")


class KerberosSettingsForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.KerberosSettings

    def save(self):
        super(KerberosSettingsForm, self).save()
        notifier().start("ix-kerberos")
