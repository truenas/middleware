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
import tempfile

from ldap import LDAPError

from django.core.exceptions import ObjectDoesNotExist
from django.forms import FileField
from django.utils.translation import ugettext_lazy as _

from dojango import forms

from freenasUI import choices
from freenasUI.common.forms import ModelForm
from freenasUI.common.freenasldap import (
    FreeNAS_ActiveDirectory,
    FreeNAS_LDAP,
)
from freenasUI.common.freenassysctl import freenas_sysctl as _fs
from freenasUI.common.pipesubr import run
from freenasUI.common.system import (
    validate_netbios_name,
    compare_netbios_names
)
from freenasUI.directoryservice import models, utils
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.middleware.notifier import notifier
from freenasUI.services.models import CIFS

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


class idmap_fruit_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_fruit
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
            'idmap_ds_type',
            'idmap_ds_id'
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


class idmap_script_Form(ModelForm):
    class Meta:
        fields = '__all__'
        model = models.idmap_script
        exclude = [
            'idmap_ds_type',
            'idmap_ds_id'
        ]


class ActiveDirectoryForm(ModelForm):

    ad_netbiosname_a = forms.CharField(
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
        initial=''
    )

    advanced_fields = [
        'ad_netbiosname_a',
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

    def __original_save(self):
        for name in (
            'ad_domainname',
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
        for name in (
            'cifs_srv_netbiosname',
            'cifs_srv_netbiosname_b',
            'cifs_srv_netbiosalias',
        ):
            setattr(
                self.cifs,
                "_original_%s" % name,
                getattr(self.cifs, name),
            )

    def __original_changed(self):
        if (
            self.instance._original_ad_domainname != self.instance.ad_domainname or
            self.cifs._original_cifs_srv_netbiosname != self.cifs.cifs_srv_netbiosname or
            self.cifs._original_cifs_srv_netbiosname_b != self.cifs.cifs_srv_netbiosname_b or
            self.cifs._original_cifs_srv_netbiosalias != self.cifs.cifs_srv_netbiosalias or
            self.instance._original_ad_allow_trusted_doms != self.instance.ad_allow_trusted_doms or
            self.instance._original_ad_use_default_domain != self.instance.ad_use_default_domain or
            self.instance._original_ad_unix_extensions != self.instance.ad_unix_extensions or
            self.instance._original_ad_verbose_logging != self.instance.ad_verbose_logging or
            self.instance._original_ad_bindname != self.instance.ad_bindname or
            self.instance._original_ad_bindpw != self.instance.ad_bindpw
        ):
            return True
        return False

    def __init__(self, *args, **kwargs):
        super(ActiveDirectoryForm, self).__init__(*args, **kwargs)
        if self.instance.ad_bindpw:
            self.fields['ad_bindpw'].required = False
        self.cifs = CIFS.objects.latest('id')
        self.__original_save()

        self.fields["ad_idmap_backend"].widget.attrs["onChange"] = (
            "activedirectory_idmap_check();"
        )

        self.fields["ad_enable"].widget.attrs["onChange"] = (
            "activedirectory_mutex_toggle();"
        )
        self.fields['ad_kerberos_principal'].choices = choices.KERBEROS_PRINCIPAL_CHOICES()
        if self.cifs:
            self.fields['ad_netbiosname_a'].initial = self.cifs.cifs_srv_netbiosname
            self.fields['ad_netbiosname_b'].initial = self.cifs.cifs_srv_netbiosname_b
            self.fields['ad_netbiosalias'].initial = self.cifs.cifs_srv_netbiosalias
        _n = notifier()
        if not _n.is_freenas():
            if _n.failover_licensed():
                from freenasUI.failover.utils import node_label_field
                node_label_field(
                    _n.failover_node(),
                    self.fields['ad_netbiosname_a'],
                    self.fields['ad_netbiosname_b'],
                )
            else:
                del self.fields['ad_netbiosname_b']
        else:
                del self.fields['ad_netbiosname_b']


    def clean_ad_netbiosname_a(self):
        netbiosname = self.cleaned_data.get("ad_netbiosname_a")
        try:
            validate_netbios_name(netbiosname)
        except Exception as e:
            raise forms.ValidationError(e)
        return netbiosname

    def clean_ad_netbiosname_b(self):
        netbiosname_a = self.cleaned_data.get("ad_netbiosname_a")
        netbiosname = self.cleaned_data.get("ad_netbiosname_b")
        if not netbiosname:
            return netbiosname
        if netbiosname_a and netbiosname_a == netbiosname:
            with client as c:
                system_dataset = c.call('systemdataset.config')
            if system_dataset['path'] == "freenas-boot":
                raise forms.ValidationError(_(
                    'When the system dataset is located on the boot device, the same NetBIOS name cannot be used on both controllers.'
                ))
        try:
            validate_netbios_name(netbiosname)
        except Exception as e:
            raise forms.ValidationError(e)
        return netbiosname

    def clean_ad_netbiosalias(self):
        netbiosalias = self.cleaned_data.get("ad_netbiosalias")
        if netbiosalias:
            try:
                validate_netbios_name(netbiosalias)
            except Exception as e:
                raise forms.ValidationError(e)
        return netbiosalias

    def clean(self):
        cdata = self.cleaned_data
        domain = cdata.get("ad_domainname")
        bindname = cdata.get("ad_bindname")
        binddn = "%s@%s" % (bindname, domain)
        bindpw = cdata.get("ad_bindpw")
        site = cdata.get("ad_site")
        netbiosname = cdata.get("ad_netbiosname_a")
        netbiosname_b = cdata.get("ad_netbiosname_b")
        ssl = cdata.get("ad_ssl")
        certificate = cdata["ad_certificate"]
        ad_kerberos_principal = cdata["ad_kerberos_principal"]
        if '---' in ad_kerberos_principal:
            cdata['ad_kerberos_principal'] = '' 
            ad_kerberos_principal = '' 

        workgroup = None

        if certificate:
            with client as c:
                certificate = c.call(
                    'certificate.query',
                    [['id', '=', certificate.id]],
                    {'get': True}
                )
            certificate = certificate['certificate_path']

        args = {
            'domain': domain,
            'site': site,
            'ssl': ssl,
            'certfile': certificate
        }

        if not cdata.get("ad_bindpw"):
            bindpw = self.instance.ad_bindpw
            cdata['ad_bindpw'] = bindpw

        if cdata.get("ad_enable") is False:
            return cdata

        if not ad_kerberos_principal:
            if not bindname:
                raise forms.ValidationError("No domain account name specified")
            if not bindpw:
                raise forms.ValidationError("No domain account password specified")

            try:
                FreeNAS_ActiveDirectory.validate_credentials(
                    domain,
                    site=site,
                    ssl=ssl,
                    certfile=certificate,
                    binddn=binddn,
                    bindpw=bindpw
                )

            except LDAPError as e:
                log.debug("LDAPError: type = %s", type(e))

                error = []
                try:
                    error.append(e.args[0]['info'])
                    error.append(e.args[0]['desc'])
                    error = ', '.join(error)

                except Exception as e:
                    error = str(e)

                raise forms.ValidationError("{0}".format(error))

            except Exception as e:
                log.debug("Exception: type = %s", type(e))
                raise forms.ValidationError('{0}.'.format(str(e)))

            args['binddn'] = binddn
            args['bindpw'] = bindpw

        else:
            args['keytab_principal'] = ad_kerberos_principal
            args['keytab_file'] = '/etc/krb5.keytab'

        if ssl in ("off", None):
            return cdata

        if not certificate:
            raise forms.ValidationError(
                "SSL/TLS specified without certificate")

        return cdata

    def save(self):
        enable = self.cleaned_data.get("ad_enable")
        fqdn = self.cleaned_data.get("ad_domainname")

        started = notifier().started(
            "activedirectory",
            timeout=_fs().directoryservice.activedirectory.timeout.started
        )
        obj = super(ActiveDirectoryForm, self).save()

        try:
            utils.get_idmap_object(obj.ds_type, obj.id, obj.ad_idmap_backend)
        except ObjectDoesNotExist:
            log.debug(
                'IDMAP backend {} entry does not exist, creating one.'.format(obj.ad_idmap_backend)
            )
            utils.get_idmap(obj.ds_type, obj.id, obj.ad_idmap_backend)

        self.cifs.cifs_srv_netbiosname = self.cleaned_data.get("ad_netbiosname_a")
        self.cifs.cifs_srv_netbiosname_b = self.cleaned_data.get("ad_netbiosname_b")
        self.cifs.cifs_srv_netbiosalias = self.cleaned_data.get("ad_netbiosalias")
        self.cifs.save()

        if enable:
            if started is True:
                timeout = _fs().directoryservice.activedirectory.timeout.restart
                try:
                    started = notifier().restart("activedirectory", timeout=timeout)
                except Exception as e:
                    raise MiddlewareError(
                        _("Active Directory restart timed out after %d seconds." % timeout),
                    )

            if started is False:
                timeout = _fs().directoryservice.activedirectory.timeout.start
                try:
                    started = notifier().start("activedirectory", timeout=timeout)
                except Exception as e:
                    raise MiddlewareError(
                        _("Active Directory start timed out after %d seconds." % timeout),
                    )
            if started is False:
                self.instance.ad_enable = False
                super(ActiveDirectoryForm, self).save()
                raise MiddlewareError(
                    _("Active Directory failed to reload."),
                )
        else:
            if started is True:
                timeout = _fs().directoryservice.activedirectory.timeout.stop
                try:
                    started = notifier().stop("activedirectory", timeout=timeout)
                except Exception as e:
                    raise MiddlewareError(
                        _("Active Directory stop timed out after %d seconds." % timeout),
                    )

        return obj


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


class LDAPForm(ModelForm):

    ldap_netbiosname_a = forms.CharField(
        max_length=120,
        label=_("NetBIOS name"),
    )
    ldap_netbiosname_b = forms.CharField(
        max_length=120,
        label=_("NetBIOS name"),
        required=False,
    )
    ldap_netbiosalias = forms.CharField(
        max_length=120,
        label=_("NetBIOS alias"),
        required=False,
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
        self.fields["ldap_enable"].widget.attrs["onChange"] = (
            "ldap_mutex_toggle();"
        )
        self.cifs = CIFS.objects.latest('id')
        if self.cifs:
            self.fields['ldap_netbiosname_a'].initial = self.cifs.cifs_srv_netbiosname
            self.fields['ldap_netbiosname_b'].initial = self.cifs.cifs_srv_netbiosname_b
            self.fields['ldap_netbiosalias'].initial = self.cifs.cifs_srv_netbiosalias
        _n = notifier()
        if not _n.is_freenas():
            if _n.failover_licensed():
                from freenasUI.failover.utils import node_label_field
                node_label_field(
                    _n.failover_node(),
                    self.fields['ldap_netbiosname_a'],
                    self.fields['ldap_netbiosname_b'],
                )
            else:
                del self.fields['ldap_netbiosname_b']
        else:
                del self.fields['ldap_netbiosname_b']

    def check_for_samba_schema(self):
        self.clean_bindpw()

        cdata = self.cleaned_data
        binddn = cdata.get("ldap_binddn")
        bindpw = cdata.get("ldap_bindpw")
        basedn = cdata.get("ldap_basedn")
        hostname = cdata.get("ldap_hostname")

        # TODO: Usage of this function has been commented, should it be removed ?
        certfile = None
        ssl = cdata.get("ldap_ssl")
        if ssl in ('start_tls', 'on'):
            certificate = cdata["ldap_certificate"]
            if certificate:
                with client as c:
                    certificate = c.call(
                        'certificate.query',
                        [['id', '=', certificate.id]],
                        {'get': True}
                    )
            certfile = certificate['certificate_path'] if certificate else None

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

    def clean_ldap_netbiosname_a(self):
        netbiosname = self.cleaned_data.get("ldap_netbiosname_a")
        try:
            validate_netbios_name(netbiosname)
        except Exception as e:
            raise forms.ValidationError(e)
        return netbiosname

    def clean_ldap_netbiosname_b(self):
        netbiosname_a = self.cleaned_data.get("ldap_netbiosname_a")
        netbiosname = self.cleaned_data.get("ldap_netbiosname_b")
        if not netbiosname:
            return netbiosname
        if netbiosname_a and netbiosname_a == netbiosname:
            raise forms.ValidationError(_(
                'NetBIOS cannot be the same as the first.'
            ))
        try:
            validate_netbios_name(netbiosname)
        except Exception as e:
            raise forms.ValidationError(e)
        return netbiosname

    def clean_ldap_netbiosalias(self):
        netbiosalias = self.cleaned_data.get("ldap_netbiosalias")
        if netbiosalias:
            try:
                validate_netbios_name(netbiosalias)
            except Exception as e:
                raise forms.ValidationError(e)
        return netbiosalias

    def clean(self):
        cdata = self.cleaned_data
        if not cdata.get("ldap_bindpw"):
            cdata["ldap_bindpw"] = self.instance.ldap_bindpw

        binddn = cdata.get("ldap_binddn")
        bindpw = cdata.get("ldap_bindpw")
        basedn = cdata.get("ldap_basedn")
        hostname = cdata.get("ldap_hostname")
        ssl = cdata.get("ldap_ssl")

        certfile = None
        if ssl in ('start_tls', 'on'):
            certificate = cdata["ldap_certificate"]
            if not certificate:
                raise forms.ValidationError(
                    "SSL/TLS specified without certificate")
            else:
                with client as c:
                    certificate = c.call(
                        'certificate.query',
                        [['id', '=', certificate.id]],
                        {'get': True}
                    )
                certfile = certificate['certificate_path']

        port = 389
        if ssl == "on":
            port = 636
        if hostname:
            parts = hostname.split(':')
            hostname = parts[0]
            if len(parts) > 1:
                port = int(parts[1])

        if cdata.get("ldap_enable") is False:
            return cdata

        # self.check_for_samba_schema()
        try:
            FreeNAS_LDAP.validate_credentials(
                hostname,
                binddn=binddn,
                bindpw=bindpw,
                basedn=basedn,
                port=port,
                certfile=certfile,
                ssl=ssl
            )
        except LDAPError as e:
            log.debug("LDAPError: type = %s", type(e))

            error = []
            try:
                error.append(e.args[0]['info'])
                error.append(e.args[0]['desc'])
                error = ', '.join(error)

            except Exception as e:
                error = str(e)

            raise forms.ValidationError("{0}".format(error))

        except Exception as e:
            log.debug("LDAPError: type = %s", type(e))
            raise forms.ValidationError("{0}".format(str(e)))

        return cdata

    def save(self):
        enable = self.cleaned_data.get("ldap_enable")

        started = notifier().started("ldap")
        obj = super(LDAPForm, self).save()
        self.cifs.cifs_srv_netbiosname = self.cleaned_data.get("ldap_netbiosname_a")
        self.cifs.cifs_srv_netbiosname_b = self.cleaned_data.get("ldap_netbiosname_b")
        self.cifs.cifs_srv_netbiosalias = self.cleaned_data.get("ldap_netbiosalias")
        self.cifs.save()

        if enable:
            if started is True:
                started = notifier().restart("ldap", timeout=_fs().directoryservice.ldap.timeout.restart)
            if started is False:
                started = notifier().start("ldap", timeout=_fs().directoryservice.ldap.timeout.start)
            if started is False:
                self.instance.ldap_enable = False
                super(LDAPForm, self).save()
                raise MiddlewareError(_("LDAP failed to reload."))
        else:
            if started is True:
                started = notifier().stop("ldap", timeout=_fs().directoryservice.ldap.timeout.stop)

        return obj

    def done(self, request, events):
        events.append("refreshById('tab_LDAP')")
        super(LDAPForm, self).done(request, events)



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
        obj = super(KerberosKeytabCreateForm, self).save()
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
