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
import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.freeadmin.models import Model, PathField
from freenasUI.middleware.notifier import notifier
from freenasUI.system.models import Certificate

log = logging.getLogger("directoryservice.models")

DS_TYPE_NONE = 0
DS_TYPE_ACTIVEDIRECTORY = 1
DS_TYPE_LDAP = 2
DS_TYPE_NIS = 3
DS_TYPE_CIFS = 5


def enum_to_directoryservice(enum):
    ds = None
    ds_dict = {
        DS_TYPE_ACTIVEDIRECTORY: 'ActiveDirectory',
        DS_TYPE_LDAP: 'LDAP',
        DS_TYPE_NIS: 'NIS',
        DS_TYPE_CIFS: 'CIFS'
    }

    try:
        ds = ds_dict[enum]
    except Exception:
        pass

    return ds


IDMAP_TYPE_NONE = 0
IDMAP_TYPE_AD = 1
IDMAP_TYPE_AUTORID = 2
IDMAP_TYPE_HASH = 3
IDMAP_TYPE_LDAP = 4
IDMAP_TYPE_NSS = 5
IDMAP_TYPE_RFC2307 = 6
IDMAP_TYPE_RID = 7
IDMAP_TYPE_TDB = 8
IDMAP_TYPE_TDB2 = 9
IDMAP_TYPE_ADEX = 10
IDMAP_TYPE_FRUIT = 11
IDMAP_TYPE_SCRIPT = 12


def idmap_to_enum(idmap_type):
    enum = IDMAP_TYPE_NONE
    idmap_dict = {
        'ad': IDMAP_TYPE_AD,
        'autorid': IDMAP_TYPE_AUTORID,
        'fruit': IDMAP_TYPE_FRUIT,
        'ldap': IDMAP_TYPE_LDAP,
        'nss': IDMAP_TYPE_NSS,
        'rfc2307': IDMAP_TYPE_RFC2307,
        'rid': IDMAP_TYPE_RID,
        'tdb': IDMAP_TYPE_TDB,
        'script': IDMAP_TYPE_SCRIPT
    }

    try:
        enum = idmap_dict[idmap_type]
    except Exception:
        pass

    return enum


def enum_to_idmap(enum):
    idmap = None
    idmap_dict = {
        IDMAP_TYPE_AD: 'ad',
        IDMAP_TYPE_AUTORID: 'autorid',
        IDMAP_TYPE_FRUIT: 'fruit',
        IDMAP_TYPE_LDAP: 'ldap',
        IDMAP_TYPE_NSS: 'nss',
        IDMAP_TYPE_RFC2307: 'rfc2307',
        IDMAP_TYPE_RID: 'rid',
        IDMAP_TYPE_TDB: 'tdb',
        IDMAP_TYPE_SCRIPT: 'script'
    }

    try:
        idmap = idmap_dict[enum]
    except Exception:
        pass

    return idmap


class Idmap_Domain(Model):
    idmap_domain_name = models.CharField(
        max_length=120,
        unique=True,
        help_text=_(
            'Short form of domain name as represented by the nETBIOSName '
            'LDAP entry in an Active Directory domain (commonly indicated as the '
            '"pre-Windows 2000" domain name). This must not be confused with the '
            'netbios host name of the server.'
        ),
        verbose_name=_("pre-Windows 2000 Domain Name"),
    )
    idmap_domain_dns_domain_name = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        verbose_name=_("DNS Domain Name"),
    )


class Idmap_DomainToBackend(Model):
    idmap_dtb_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_dtb_idmap_backend = models.CharField(
        choices=choices.IDMAP_CHOICES(),
        default='rid',
        max_length=120,
        verbose_name=_("idmap backend for domain"),
    )


class idmap_ad(Model):
    idmap_ad_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_ad_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=10000
    )
    idmap_ad_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=90000000
    )
    idmap_ad_schema_mode = models.CharField(
        verbose_name=_("Schema Mode"),
        max_length=120,
        help_text=_(
            'Defines the schema that idmap_ad should use when querying '
            'Active Directory regarding user and group information. '
            'This can be either the RFC2307 schema support included '
            'in Windows 2003 R2 or the Service for Unix (SFU) schema. '
            'For SFU 3.0 or 3.5 please choose "sfu", for SFU 2.0 please '
            'choose "sfu20". Please note that primary group membership '
            'is currently always calculated via the "primaryGroupID" '
            'LDAP attribute.'
        ),
        choices=(
            ('rfc2307', _('rfc2307')),
            ('sfu', _('sfu')),
            ('sfu20', _('sfu20')),
        ),
        default='rfc2307'
    )
    idmap_ad_unix_primary_group = models.BooleanField(
        verbose_name=_("UNIX Primary Group"),
        help_text=_(
            'Defines whether the user\'s primary group is fetched from the SFU '
            'attributes or the AD primary group. If set to yes the primary group '
            'membership is fetched from the LDAP attributes (gidNumber). If set '
            'to no the primary group membership is calculated via the '
            '"primaryGroupID" LDAP attribute.'
        ),
        default=False
    )
    idmap_ad_unix_nss_info = models.BooleanField(
        verbose_name=_("UNIX NSS Info"),
        help_text=_(
            'If set to yes winbind will retrieve the login shell and home '
            'directory from the LDAP attributes. If set to no the or the AD LDAP '
            'entry lacks the SFU attributes the options template shell and '
            'template homedir are used.'
        ),
        default=False
    )

    def __init__(self, *args, **kwargs):
        super(idmap_ad, self).__init__(*args, **kwargs)

    class Meta:
        verbose_name = _("AD Idmap")
        verbose_name_plural = _("AD Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/ad'


class idmap_autorid(Model):
    idmap_autorid_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_autorid_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=10000
    )
    idmap_autorid_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=90000000
    )
    idmap_autorid_rangesize = models.IntegerField(
        verbose_name=_("Range Size"),
        help_text=_(
            "Defines the number of uids/gids available per domain range. "
            "The minimum needed value is 2000. SIDs with RIDs larger "
            "than this value will be mapped into extension ranges "
            "depending upon number of available ranges. If the autorid "
            "backend runs out of available ranges, mapping requests for "
            "new domains (or new extension ranges for domains already "
            "known) are ignored and the corresponding map is discarded."
        ),
        default=100000
    )
    idmap_autorid_readonly = models.BooleanField(
        verbose_name=_("Read Only"),
        help_text=_(
            "Turn the module into read-only mode. No new ranges will "
            "be allocated nor will new mappings be created in the "
            "idmap pool."
        ),
        default=False
    )
    idmap_autorid_ignore_builtin = models.BooleanField(
        verbose_name=_("Ignore Builtin"),
        help_text=_("Ignore any mapping requests for the BUILTIN domain."),
        default=False
    )

    def __init__(self, *args, **kwargs):
        super(idmap_autorid, self).__init__(*args, **kwargs)

    class Meta:
        verbose_name = _("AutoRID Idmap")
        verbose_name_plural = _("AutoRID Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/autorid'


class idmap_fruit(Model):
    idmap_fruit_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_fruit_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=90000001
    )
    idmap_fruit_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=100000000
    )

    def __init__(self, *args, **kwargs):
        super(idmap_fruit, self).__init__(*args, **kwargs)

    class Meta:
        verbose_name = _("Fruit Idmap")
        verbose_name_plural = _("Fruit Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/fruit'


class idmap_ldap(Model):
    idmap_ldap_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_ldap_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=10000
    )
    idmap_ldap_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=90000000
    )
    idmap_ldap_ldap_base_dn = models.CharField(
        verbose_name=_("Base DN"),
        max_length=120,
        help_text=_(
            'Defines the directory base suffix to use for SID/uid/gid '
            'mapping entries. If not defined, idmap_ldap will default '
            'to using the "ldap idmap suffix" option from smb.conf.'
        ),
        blank=True
    )
    idmap_ldap_ldap_user_dn = models.CharField(
        verbose_name=_("User DN"),
        max_length=120,
        help_text=_(
            "Defines the user DN to be used for authentication. The "
            "secret for authenticating this user should be stored with "
            "net idmap secret (see net(8)). If absent, the ldap "
            "credentials from the ldap passdb configuration are used, "
            "and if these are also absent, an anonymous bind will be "
            "performed as last fallback."
        ),
        blank=True
    )
    idmap_ldap_ldap_url = models.CharField(
        verbose_name=_("URL"),
        max_length=255,
        help_text=_(
            "Specifies the LDAP server to use for "
            "SID/uid/gid map entries."
        )
    )
    idmap_ldap_ssl = models.CharField(
        verbose_name=_("Encryption Mode"),
        max_length=120,
        help_text=_(
            "This parameter specifies whether to use SSL/TLS, e.g."
            " on/off/start_tls"
        ),
        choices=choices.LDAP_SSL_CHOICES,
        default='off'
    )
    idmap_ldap_certificate = models.ForeignKey(
        Certificate,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        limit_choices_to={'cert_certificate__isnull': False, 'cert_privatekey__isnull': False}
    )

    def __init__(self, *args, **kwargs):
        super(idmap_ldap, self).__init__(*args, **kwargs)

    def get_url(self):
        return self.idmap_ldap_ldap_url

    def get_ssl(self):
        return self.idmap_ldap_ssl

    def get_certificate(self):
        return self.idmap_ldap_certificate

    class Meta:
        verbose_name = _("LDAP Idmap")
        verbose_name_plural = _("LDAP Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/ldap'


class idmap_nss(Model):
    idmap_nss_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_nss_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=10000
    )
    idmap_nss_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=90000000
    )

    def __init__(self, *args, **kwargs):
        super(idmap_nss, self).__init__(*args, **kwargs)

    class Meta:
        verbose_name = _("NSS Idmap")
        verbose_name_plural = _("NSS Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/nss'


class idmap_rfc2307(Model):
    idmap_rfc2307_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_rfc2307_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=10000
    )
    idmap_rfc2307_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=90000000
    )
    idmap_rfc2307_ldap_server = models.CharField(
        verbose_name=_("LDAP Server"),
        max_length=120,
        help_text=_(
            "Defines the type of LDAP server to use. This can either "
            "be the LDAP server provided by the Active Directory server "
            "(ad) or a stand-alone LDAP server."
        ),
        choices=(
            ('ad', _('ad')),
            ('stand-alone', _('stand-alone')),
        ),
        default='ad'
    )
    idmap_rfc2307_bind_path_user = models.CharField(
        verbose_name=_("User Bind Path"),
        max_length=120,
        help_text=_(
            "Specifies the bind path where user objects "
            "can be found in the LDAP server."
        )
    )
    idmap_rfc2307_bind_path_group = models.CharField(
        verbose_name=_("Group Bind Path"),
        max_length=120,
        help_text=_(
            "Specifies the bind path where group objects can "
            "be found in the LDAP server."
        )
    )
    idmap_rfc2307_user_cn = models.BooleanField(
        verbose_name=_("User CN"),
        help_text=_(
            "Query cn attribute instead of uid attribute "
            "for the user name in LDAP."
        ),
        default=False
    )
    idmap_rfc2307_cn_realm = models.BooleanField(
        verbose_name=_("CN Realm"),
        help_text=_(
            "Append @realm to cn for groups (and users if "
            "user_cn is set) in LDAP."
        ),
        default=False
    )
    idmap_rfc2307_ldap_domain = models.CharField(
        verbose_name=_("LDAP Domain"),
        max_length=120,
        help_text=_(
            "When using the LDAP server in the Active Directory server, "
            "this allows to specify the domain where to access the "
            "Active Directory server. This allows using trust "
            "relationships while keeping all RFC 2307 records in one "
            "place. This parameter is optional, the default is to "
            "access the AD server in the current domain to query LDAP"
            "records."
        ),
        blank=True
    )
    idmap_rfc2307_ldap_url = models.CharField(
        verbose_name=_("LDAP URL"),
        max_length=255,
        help_text=_(
            "When using a stand-alone LDAP server, this "
            "parameter specifies the ldap URL for accessing the LDAP server."
        ),
        blank=True
    )
    idmap_rfc2307_ldap_user_dn = models.CharField(
        verbose_name=_("LDAP User DN"),
        max_length=120,
        help_text=_(
            "Defines the user DN to be used for authentication. The "
            "secret for authenticating this user should be stored with "
            "net idmap secret (see net(8)). If absent, an anonymous "
            "bind will be performed."
        ),
        blank=True
    )
    idmap_rfc2307_ldap_user_dn_password = models.CharField(
        verbose_name=_("LDAP User DN Password"),
        max_length=120,
        help_text=_("Password for LDAP User DN"),
        blank=True
    )
    idmap_rfc2307_ldap_realm = models.CharField(
        verbose_name=_("LDAP Realm"),
        max_length=120,
        help_text=_(
            "Defines the realm to use in the user and group names. "
            "This is only required when using cn_realm together with "
            "a stand-alone ldap server."
        ),
        blank=True
    )
    idmap_rfc2307_ssl = models.CharField(
        verbose_name=_("Encryption Mode"),
        max_length=120,
        help_text=_(
            "This parameter specifies whether to use SSL/TLS, e.g."
            " on/off/start_tls"
        ),
        choices=choices.LDAP_SSL_CHOICES,
        default='off'
    )
    idmap_rfc2307_certificate = models.ForeignKey(
        Certificate,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        limit_choices_to={'cert_certificate__isnull': False, 'cert_privatekey__isnull': False}
    )

    def __init__(self, *args, **kwargs):
        super(idmap_rfc2307, self).__init__(*args, **kwargs)

        if self.idmap_rfc2307_ldap_user_dn_password:
            try:
                self.idmap_rfc2307_ldap_user_dn_password = notifier().pwenc_decrypt(
                    self.idmap_rfc2307_ldap_user_dn_password
                )
            except Exception:
                log.debug('Failed to decrypt idmap password', exc_info=True)
                self.idmap_rfc2307_ldap_user_dn_password = ''

        self._idmap_rfc2307_ldap_user_dn_password_encrypted = False

    def get_url(self):
        return self.idmap_rfc2307_ldap_url

    def get_ssl(self):
        return self.idmap_rfc2307_ssl

    def get_certificate(self):
        return self.idmap_rfc2307_certificate

    def save(self, *args, **kwargs):
        if self.idmap_rfc2307_ldap_user_dn_password and \
                not self._idmap_rfc2307_ldap_user_dn_password_encrypted:
            self.idmap_rfc2307_ldap_user_dn_password = notifier().pwenc_encrypt(
                self.idmap_rfc2307_ldap_user_dn_password
            )
            self._idmap_rfc2307_ldap_user_dn_password_encrypted = True
        super(idmap_rfc2307, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("RFC2307 Idmap")
        verbose_name_plural = _("RFC2307 Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/rfc2307'


class idmap_rid(Model):
    idmap_rid_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_rid_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=20000
    )
    idmap_rid_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=90000000
    )

    def __init__(self, *args, **kwargs):
        super(idmap_rid, self).__init__(*args, **kwargs)

    class Meta:
        verbose_name = _("RID Idmap")
        verbose_name_plural = _("RID Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/rid'


class idmap_tdb(Model):
    idmap_tdb_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_tdb_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=90000001
    )
    idmap_tdb_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=100000000
    )

    def __init__(self, *args, **kwargs):
        super(idmap_tdb, self).__init__(*args, **kwargs)

    class Meta:
        verbose_name = _("TDB Idmap")
        verbose_name_plural = _("TDB Idmap")

    class FreeAdmin:
        deletable = False
        resource_name = 'directoryservice/idmap/tdb'


class idmap_script(Model):
    idmap_script_domain = models.OneToOneField(
        Idmap_Domain,
        on_delete=models.deletion.CASCADE,
        to_field='idmap_domain_name',
        unique=True, null=True,
        verbose_name=_('pre-Windows 2000 Domain Name'),
    )
    idmap_script_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=90000001
    )
    idmap_script_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=100000000
    )
    idmap_script_script = PathField(
        verbose_name=_("Script"),
        help_text=_(
            "This option is used to configure an external program for "
            "performing id mappings. This is read-only backend and relies on "
            "winbind_cache tdb to store obtained values"
        )
    )

    def __init__(self, *args, **kwargs):
        super(idmap_script, self).__init__(*args, **kwargs)

    class Meta:
        verbose_name = _("Script Idmap")
        verbose_name_plural = _("Script Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/script'


class KerberosRealm(Model):
    krb_realm = models.CharField(
        verbose_name=_("Realm"),
        max_length=120,
        help_text=_("Kerberos realm."),
        unique=True
    )
    krb_kdc = models.CharField(
        verbose_name=_("KDC"),
        max_length=120,
        help_text=_("KDC for this realm."),
        blank=True
    )
    krb_admin_server = models.CharField(
        verbose_name=_("Admin Server"),
        max_length=120,
        help_text=_(
            "Specifies the admin server for this realm, where all the "
            "modifications to the database are performed."
        ),
        blank=True
    )
    krb_kpasswd_server = models.CharField(
        verbose_name=_("Password Server"),
        max_length=120,
        help_text=_(
            "Points to the server where all the password changes are "
            "performed.  If there is no such entry, the kpasswd port "
            "on the admin_server host will be tried."
        ),
        blank=True
    )

    def __str__(self):
        return self.krb_realm


class KerberosKeytab(Model):
    keytab_name = models.CharField(
        verbose_name=_("Name"),
        max_length=120,
        help_text=_("Descriptive Name."),
        unique=True
    )
    keytab_file = models.TextField(
        verbose_name=_("Keytab"),
        help_text=_("Kerberos keytab file")
    )

    def delete(self):
        super(KerberosKeytab, self).delete()

    def __str__(self):
        return self.keytab_name


class KerberosSettings(Model):
    ks_appdefaults_aux = models.TextField(
        verbose_name=_("Appdefaults auxiliary parameters"),
        blank=True
    )
    ks_libdefaults_aux = models.TextField(
        verbose_name=_("Libdefaults auxiliary parameters"),
        blank=True
    )

    class Meta:
        verbose_name = _("Kerberos Settings")
        verbose_name_plural = _("Kerberos Settings")


class DirectoryServiceBase(Model):
    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(DirectoryServiceBase, self).__init__(*args, **kwargs)

        self.ds_type = DS_TYPE_NONE
        self.ds_name = enum_to_directoryservice(self.ds_type)


class ActiveDirectory(DirectoryServiceBase):
    ad_domainname = models.CharField(
        verbose_name=_("Domain Name (DNS/Realm-Name)"),
        max_length=120,
        help_text=_("Domain Name, eg example.com")
    )
    ad_bindname = models.CharField(
        verbose_name=_("Domain Account Name"),
        max_length=120,
        help_text=_("Domain account name to bind as"),
        blank=True
    )
    ad_bindpw = models.CharField(
        verbose_name=_("Domain Account Password"),
        max_length=120,
        help_text=_("Domain Account password."),
        blank=True
    )
    ad_ssl = models.CharField(
        verbose_name=_("Encryption Mode"),
        max_length=120,
        help_text=_(
            "This parameter specifies whether to use SSL/TLS, e.g."
            " on/off/start_tls"
        ),
        choices=choices.LDAP_SSL_CHOICES,
        default='off'
    )
    ad_certificate = models.ForeignKey(
        Certificate,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        limit_choices_to={'cert_certificate__isnull': False, 'cert_privatekey__isnull': False}
    )
    ad_verbose_logging = models.BooleanField(
        verbose_name=_("Verbose logging"),
        default=False
    )
    ad_allow_trusted_doms = models.BooleanField(
        verbose_name=_("Allow Trusted Domains"),
        help_text=_("Set this if you want to allow Trusted Domains."),
        default=False
    )
    ad_use_default_domain = models.BooleanField(
        verbose_name=_("Use Default Domain"),
        help_text=_(
            "Set this if you want to use the default "
            "domain for users and groups."),
        default=False
    )
    ad_allow_dns_updates = models.BooleanField(
        verbose_name=_("Allow DNS updates"),
        help_text=_("Set this if you want to allow allow DNS updates."),
        default=True
    )
    ad_disable_freenas_cache = models.BooleanField(
        verbose_name=_("Disable Active Directory user/group cache"),
        help_text=_(
            "Set this if you want to disable caching Active Directory users "
            "and groups. Use this option if you are experiencing slowness or "
            "having difficulty binding to the domain with a large number of "
            "users and groups."),
        default=False
    )
    ad_site = models.CharField(
        verbose_name=_("Site Name"),
        max_length=120,
        help_text=_(
            "Name of Active Directory Site. This field will be automatically populated "
            "during the domain join process. If an AD site is not configured for the "
            "subnet where the NAS is located, the site name will be populated as "
            "'Default-First-Site-Name'"),
        blank=True,
        null=True
    )
    ad_kerberos_realm = models.ForeignKey(
        KerberosRealm,
        verbose_name=_("Kerberos Realm"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    ad_kerberos_principal = models.CharField(
        verbose_name=_("Kerberos Princpal"),
        max_length=255,
        help_text=_(
            "Kerberos principal to use for AD-related UI and middleware operations "
            "Field is populated with principals present in the system keytab. "
            "During the domain join process a keytab entry is generated for the "
            "AD Machine Account associated with the NAS. The name for this account "
            "is the netbios name of the server with a '$' appended to it. Once "
            "the NAS is joined to active directory, the bind credentials will be "
            "automatically cleared and all future operations carried out by the AD "
            "machine account, which has a restricted set of privileges in the AD domain."),
        blank=True,
	null=True
    )
    ad_createcomputer = models.CharField(
        blank=True,
        max_length=255,
        verbose_name=_('Computer Account OU'),
        help_text=(
            'If blank, then the default OU is used during computer account creation. '
            'Precreate the computer account in a specific OU. The OU string '
            'read from top to bottom without RDNs and delimited by a "/". '
            'E.g. "createcomputer=Computers/Servers/Unix NB: A backslash '
            '"\" is used as escape at multiple levels and may need to be '
            'doubled or even quadrupled. It is not used as a separator.'
        )
    )
    ad_timeout = models.IntegerField(
        verbose_name=_("AD timeout"),
        help_text=_("Timeout for AD related commands."),
        default=60
    )
    ad_dns_timeout = models.IntegerField(
        verbose_name=_("DNS timeout"),
        help_text=_("Timeout for AD DNS queries."),
        default=60
    )
    ad_idmap_backend = models.CharField(
        verbose_name=_("Idmap backend"),
        choices=choices.IDMAP_CHOICES(),
        max_length=120,
        help_text=_("Idmap backend for winbind."),
        default=enum_to_idmap(IDMAP_TYPE_RID)
    )
    ad_nss_info = models.CharField(
        max_length=120,
        blank=True,
        null=True,
        choices=choices.NSS_INFO_CHOICES,
        verbose_name=_("Winbind NSS Info"),
        help_text=_("This parameter is designed to control how Winbind "
                    "retrieves Name Service Information to construct a user's "
                    "home directory and login")
    )
    ad_ldap_sasl_wrapping = models.CharField(
        verbose_name=_("SASL wrapping"),
        choices=choices.LDAP_SASL_WRAPPING_CHOICES,
        max_length=120,
        help_text=_("The client ldap sasl wrapping defines whether ldap "
                    "traffic will be signed or signed and encrypted (sealed)."
                    "This option is needed in the case of Domain Controllers "
                    "enforcing the usage of signed LDAP connections (e.g. "
                    "Windows 2000 SP3 or higher). LDAP sign and seal can be "
                    "controlled with the registry key \"HKLM\System\\"
                    "CurrentControlSet\\Services\\NTDS\\Parameters\\"
                    "LDAPServerIntegrity\" on the Windows server side."
                    ),
        default='plain'
    )
    ad_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False
    )

    def __init__(self, *args, **kwargs):
        super(ActiveDirectory, self).__init__(*args, **kwargs)

        if self.ad_bindpw:
            try:
                self.ad_bindpw = notifier().pwenc_decrypt(self.ad_bindpw)
            except Exception:
                log.debug('Failed to decrypt AD bind password', exc_info=True)
                self.ad_bindpw = ''
        self._ad_bindpw_encrypted = False

        self.ds_type = DS_TYPE_ACTIVEDIRECTORY
        self.ds_name = enum_to_directoryservice(self.ds_type)

    def save(self, **kwargs):
        if self.ad_bindpw and not self._ad_bindpw_encrypted:
            self.ad_bindpw = notifier().pwenc_encrypt(
                self.ad_bindpw
            )
            self._ad_bindpw_encrypted = True
        super(ActiveDirectory, self).save(**kwargs)

    class Meta:
        verbose_name = _("Active Directory")
        verbose_name_plural = _("Active Directory")


class NIS(DirectoryServiceBase):
    nis_domain = models.CharField(
        verbose_name=_("NIS domain"),
        max_length=120,
        help_text=_("NIS domain name")
    )
    nis_servers = models.CharField(
        verbose_name=_("NIS servers"),
        max_length=8192,
        help_text=_("Comma delimited list of NIS servers"),
        blank=True
    )
    nis_secure_mode = models.BooleanField(
        verbose_name=_("Secure mode"),
        help_text=_("Cause ypbind to run in secure mode"),
        default=False
    )
    nis_manycast = models.BooleanField(
        verbose_name=_("Manycast"),
        help_text=_("Cause ypbind to use 'many-cast' instead of broadcast"),
        default=False
    )
    nis_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False,
    )

    def __init__(self, *args, **kwargs):
        super(NIS, self).__init__(*args, **kwargs)

        self.ds_type = DS_TYPE_NIS
        self.ds_name = enum_to_directoryservice(self.ds_type)

    class Meta:
        verbose_name = _("NIS Domain")
        verbose_name_plural = _("NIS Domain")


class LDAP(DirectoryServiceBase):
    ldap_hostname = models.CharField(
        verbose_name=_("Hostname"),
        max_length=120,
        help_text=_("The name or IP address of the LDAP server"),
        blank=True
    )
    ldap_basedn = models.CharField(
        verbose_name=_("Base DN"),
        max_length=120,
        help_text=_(
            "The default base Distinguished Name (DN) to use for "
            "searches, eg dc=test,dc=org"),
        blank=True
    )
    ldap_binddn = models.CharField(
        verbose_name=_("Bind DN"),
        max_length=256,
        help_text=_(
            "The distinguished name with which to bind to the "
            "directory server, e.g. cn=admin,dc=test,dc=org"),
        blank=True
    )
    ldap_bindpw = models.CharField(
        verbose_name=_("Bind password"),
        max_length=120,
        help_text=_("The credentials with which to bind."),
        blank=True
    )
    ldap_anonbind = models.BooleanField(
        verbose_name=_("Allow Anonymous Binding"),
        default=False
    )
    ldap_usersuffix = models.CharField(
        verbose_name=_("User Suffix"),
        max_length=120,
        help_text=_(
            "This parameter specifies the suffix that is used for "
            "users when these are added to the LDAP directory, e.g. "
            "ou=Users"),
        blank=True
    )
    ldap_groupsuffix = models.CharField(
        verbose_name=_("Group Suffix"),
        max_length=120,
        help_text=_(
            "This parameter specifies the suffix that is used "
            "for groups when these are added to the LDAP directory, e.g. "
            "ou=Groups"),
        blank=True
    )
    ldap_passwordsuffix = models.CharField(
        verbose_name=_("Password Suffix"),
        max_length=120,
        help_text=_(
            "This parameter specifies the suffix that is used for "
            "passwords when these are added to the LDAP directory, e.g. "
            "ou=Passwords"),
        blank=True
    )
    ldap_machinesuffix = models.CharField(
        verbose_name=_("Machine Suffix"),
        max_length=120,
        help_text=_(
            "This parameter specifies the suffix that is used for "
            "machines when these are added to the LDAP directory, e.g. "
            "ou=Computers"),
        blank=True
    )
    ldap_sudosuffix = models.CharField(
        verbose_name=_("SUDO Suffix"),
        max_length=120,
        help_text=_(
            "This parameter specifies the suffix that is used for "
            "the SUDO configuration in the LDAP directory, e.g. "
            "ou=SUDOers"),
        blank=True
    )
    ldap_kerberos_realm = models.ForeignKey(
        KerberosRealm,
        verbose_name=_("Kerberos Realm"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    ldap_kerberos_principal = models.CharField(
        verbose_name=_("Kerberos Princpal"),
        max_length=255,
        blank=True
    )
    ldap_ssl = models.CharField(
        verbose_name=_("Encryption Mode"),
        max_length=120,
        help_text=_(
            "This parameter specifies whether to use SSL/TLS, e.g."
            " on/off/start_tls"
        ),
        choices=choices.LDAP_SSL_CHOICES,
        default='off'
    )
    ldap_certificate = models.ForeignKey(
        Certificate,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        limit_choices_to={'cert_certificate__isnull': False, 'cert_privatekey__isnull': False}
    )
    ldap_disable_freenas_cache = models.BooleanField(
        verbose_name=_("Disable LDAP user/group cache"),
        help_text=_(
            "Set to disable caching LDAP users "
            "and groups. This is an optimization for large LDAP "
            "Environments. When caching is disabled, LDAP users "
            "and groups do not appear in dropdown menus, but are "
            "still accepted in relevant form fields if manually entered."
        ),
        default=False
    )
    ldap_timeout = models.IntegerField(
        verbose_name=_("LDAP timeout"),
        help_text=_("Timeout for LDAP related commands."),
        default=10
    )
    ldap_dns_timeout = models.IntegerField(
        verbose_name=_("DNS timeout"),
        help_text=_("Timeout for LDAP DNS queries."),
        default=10
    )
    ldap_idmap_backend = models.CharField(
        verbose_name=_("Idmap Backend"),
        choices=choices.IDMAP_CHOICES(),
        max_length=120,
        help_text=_("Idmap backend for winbind."),
        default=enum_to_idmap(IDMAP_TYPE_LDAP)
    )
    ldap_has_samba_schema = models.BooleanField(
        verbose_name=_("Samba Schema"),
        default=False
    )
    ldap_auxiliary_parameters = models.TextField(
        verbose_name=_("Auxiliary Parameters"),
        blank=True,
        help_text=_("These parameters are added to nslcd.conf")
    )
    ldap_schema = models.CharField(
        verbose_name=("Schema"),
        choices=choices.LDAP_SCHEMA_CHOICES,
        max_length=120,
        help_text=_("LDAP Schema type."),
        default=choices.LDAP_SCHEMA_CHOICES[0][0]
    )
    ldap_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False
    )

    def __init__(self, *args, **kwargs):
        super(LDAP, self).__init__(*args, **kwargs)

        if self.ldap_bindpw:
            try:
                self.ldap_bindpw = notifier().pwenc_decrypt(self.ldap_bindpw)
            except Exception:
                log.debug(
                    'Failed to decrypt LDAP bind password',
                    exc_info=True
                )
                self.ldap_bindpw = ''
        self._ldap_bindpw_encrypted = False

        self.ds_type = DS_TYPE_LDAP
        self.ds_name = enum_to_directoryservice(self.ds_type)

    def save(self, *args, **kwargs):
        if self.ldap_bindpw and not self._ldap_bindpw_encrypted:
            self.ldap_bindpw = notifier().pwenc_encrypt(
                self.ldap_bindpw
            )
            self._ldap_bindpw_encrypted = True
        super(LDAP, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("LDAP")
        verbose_name_plural = _("LDAP")
