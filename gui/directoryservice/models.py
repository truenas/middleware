#
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
import re

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.freeadmin.models import Model, PathField
from freenasUI.middleware.notifier import notifier
from freenasUI.system.models import CertificateAuthority

log = logging.getLogger("directoryservice.models")

DS_TYPE_NONE = 0
DS_TYPE_ACTIVEDIRECTORY = 1
DS_TYPE_LDAP = 2
DS_TYPE_NIS = 3
DS_TYPE_NT4 = 4
DS_TYPE_CIFS = 5


def directoryservice_to_enum(ds_type):
    enum = DS_TYPE_NONE
    ds_dict = {
        'ActiveDirectory': DS_TYPE_ACTIVEDIRECTORY,
        'LDAP': DS_TYPE_LDAP,
        'NIS': DS_TYPE_NIS,
        'NT4': DS_TYPE_NT4,
        'CIFS': DS_TYPE_CIFS,
    }

    try:
        enum = ds_dict[ds_type]
    except:
        pass

    return enum


def enum_to_directoryservice(enum):
    ds = None
    ds_dict = {
        DS_TYPE_ACTIVEDIRECTORY: 'ActiveDirectory',
        DS_TYPE_LDAP: 'LDAP',
        DS_TYPE_NIS: 'NIS',
        DS_TYPE_NT4: 'NT4',
        DS_TYPE_CIFS: 'CIFS'
    }

    try:
        ds = ds_dict[enum]
    except:
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


def idmap_to_enum(idmap_type):
    enum = IDMAP_TYPE_NONE
    idmap_dict = {
        'ad': IDMAP_TYPE_AD,
        'adex': IDMAP_TYPE_ADEX,
        'autorid': IDMAP_TYPE_AUTORID,
        'hash': IDMAP_TYPE_HASH,
        'ldap': IDMAP_TYPE_LDAP,
        'nss': IDMAP_TYPE_NSS,
        'rfc2307': IDMAP_TYPE_RFC2307,
        'rid': IDMAP_TYPE_RID,
        'tdb': IDMAP_TYPE_TDB,
        'tdb2': IDMAP_TYPE_TDB2
    }

    try:
        enum = idmap_dict[idmap_type]
    except:
        pass

    return enum


def enum_to_idmap(enum):
    idmap = None
    idmap_dict = {
        IDMAP_TYPE_AD: 'ad',
        IDMAP_TYPE_ADEX: 'adex',
        IDMAP_TYPE_AUTORID: 'autorid',
        IDMAP_TYPE_HASH: 'hash',
        IDMAP_TYPE_LDAP: 'ldap',
        IDMAP_TYPE_NSS: 'nss',
        IDMAP_TYPE_RFC2307: 'rfc2307',
        IDMAP_TYPE_RID: 'rid',
        IDMAP_TYPE_TDB: 'tdb',
        IDMAP_TYPE_TDB2: 'tdb2'
    }

    try:
        idmap = idmap_dict[enum]
    except:
        pass

    return idmap


class idmap_base(Model):
    idmap_ds_type = models.IntegerField(
        null=True
    )
    idmap_ds_id = models.PositiveIntegerField(
        null=True
    )

    def __init__(self, *args, **kwargs):
        super(idmap_base, self).__init__(*args, **kwargs)

        self.idmap_backend_type = IDMAP_TYPE_NONE
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

        if 'idmap_ds_type' in kwargs:
            self.idmap_ds_type = kwargs['idmap_ds_type']
        if 'idmap_ds_id' in kwargs:
            self.idmap_ds_id = kwargs['idmap_ds_id']

    def __unicode__(self):
        return self.idmap_backend_name

    class Meta:
        abstract = True


class idmap_ad(idmap_base):
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

    def __init__(self, *args, **kwargs):
        super(idmap_ad, self).__init__(*args, **kwargs)

        self.idmap_backend_type = IDMAP_TYPE_AD
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("AD Idmap")
        verbose_name_plural = _("AD Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/ad'


class idmap_adex(idmap_base):
    idmap_adex_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=10000
    )
    idmap_adex_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=90000000
    )

    def __init__(self, *args, **kwargs):
        super(idmap_adex, self).__init__(*args, **kwargs)

        self.idmap_backend_type = IDMAP_TYPE_ADEX
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("ADEX Idmap")
        verbose_name_plural = _("ADEX Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/adex'


class idmap_autorid(idmap_base):
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

        self.idmap_backend_type = IDMAP_TYPE_AUTORID
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("AutoRID Idmap")
        verbose_name_plural = _("AutoRID Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/autorid'


class idmap_hash(idmap_base):
    idmap_hash_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=90000001
    )
    idmap_hash_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=100000000
    )
    idmap_hash_range_name_map = PathField(
        verbose_name=_("Name Map"),
        help_text=_(
            'Specifies the absolute path to the name mapping file '
            'used by the nss_info API. Entries in the file are of '
            'the form "unix name = qualified domain name". Mapping '
            'of both user and group names is supported.'
        )
    )

    def __init__(self, *args, **kwargs):
        super(idmap_hash, self).__init__(*args, **kwargs)

        self.idmap_backend_type = IDMAP_TYPE_HASH
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("Hash Idmap")
        verbose_name_plural = _("Hash Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/hash'


class idmap_ldap(idmap_base):
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
        CertificateAuthority,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    def __init__(self, *args, **kwargs):
        super(idmap_ldap, self).__init__(*args, **kwargs)

        self.idmap_backend_type = IDMAP_TYPE_LDAP
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

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


class idmap_nss(idmap_base):
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

        self.idmap_backend_type = IDMAP_TYPE_NSS
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("NSS Idmap")
        verbose_name_plural = _("NSS Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/nss'


class idmap_rfc2307(idmap_base):
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
        CertificateAuthority,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    def __init__(self, *args, **kwargs):
        super(idmap_rfc2307, self).__init__(*args, **kwargs)

        self.idmap_backend_type = IDMAP_TYPE_RFC2307
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

        if self.idmap_rfc2307_ldap_user_dn_password:
            try:
                self.idmap_rfc2307_ldap_user_dn_password = notifier().pwenc_decrypt(
                    self.idmap_rfc2307_ldap_user_dn_password
                )
            except:
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


class idmap_rid(idmap_base):
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

        self.idmap_backend_type = IDMAP_TYPE_RID
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("RID Idmap")
        verbose_name_plural = _("RID Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/rid'


class idmap_tdb(idmap_base):
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

        self.idmap_backend_type = IDMAP_TYPE_TDB
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("TDB Idmap")
        verbose_name_plural = _("TDB Idmap")

    class FreeAdmin:
        deletable = False


class idmap_tdb2(idmap_base):
    idmap_tdb2_range_low = models.IntegerField(
        verbose_name=_("Range Low"),
        default=90000001
    )
    idmap_tdb2_range_high = models.IntegerField(
        verbose_name=_("Range High"),
        default=100000000
    )
    idmap_tdb2_script = PathField(
        verbose_name=_("Script"),
        help_text=_(
            "This option can be used to configure an external program for "
            "performing id mappings instead of using the tdb counter. The "
            "mappings are then stored int tdb2 idmap database."
        )
    )

    def __init__(self, *args, **kwargs):
        super(idmap_tdb2, self).__init__(*args, **kwargs)

        self.idmap_backend_type = IDMAP_TYPE_TDB2
        self.idmap_backend_name = enum_to_idmap(self.idmap_backend_type)

    class Meta:
        verbose_name = _("TDB2 Idmap")
        verbose_name_plural = _("TDB2 Idmap")

    class FreeAdmin:
        resource_name = 'directoryservice/idmap/tdb2'


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

    def __unicode__(self):
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
        KerberosPrincipal.objects.filter(
            principal_keytab=self
        ).delete()
        super(KerberosKeytab, self).delete()

    def __unicode__(self):
        return self.keytab_name


class KerberosPrincipal(Model):
    principal_keytab = models.ForeignKey(
        KerberosKeytab,
        verbose_name=_("Keytab"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    principal_version = models.IntegerField(
        verbose_name=_("Version number"),
        default=-1
    )
    principal_encryption = models.CharField(
        verbose_name=_("Encryption algorithm"),
        max_length=120
    )
    principal_name = models.CharField(
        verbose_name=_("Principal name"),
        max_length=120
    )
    principal_timestamp = models.DateTimeField(
        verbose_name=_("Date")
    )

    def __unicode__(self):
        return self.principal_name


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


class NT4(DirectoryServiceBase):
    nt4_dcname = models.CharField(
        verbose_name=_("Domain Controller"),
        max_length=120,
        help_text=_("FQDN of the domain controller to use."),
    )
    nt4_netbiosname = models.CharField(
        verbose_name=_("NetBIOS Name"),
        max_length=120,
        help_text=_("System hostname"),
        blank=True
    )
    nt4_workgroup = models.CharField(
        verbose_name=_("Workgroup Name"),
        max_length=120,
        help_text=_("Workgroup or domain name in old format, eg WORKGROUP")
    )
    nt4_adminname = models.CharField(
        verbose_name=_("Administrator Name"),
        max_length=120,
        help_text=_("Domain administrator account name")
    )
    nt4_adminpw = models.CharField(
        verbose_name=_("Administrator Password"),
        max_length=120,
        help_text=_("Domain administrator account password.")
    )
    nt4_use_default_domain = models.BooleanField(
        verbose_name=_("Use Default Domain"),
        help_text=_(
            "Set this if you want to use the default "
            "domain for users and groups."),
        default=False
    )
    nt4_idmap_backend = models.CharField(
        verbose_name=_("Idmap backend"),
        choices=choices.IDMAP_CHOICES,
        max_length=120,
        help_text=_("Idmap backend for winbind."),
        default=enum_to_idmap(IDMAP_TYPE_RID)
    )
    nt4_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False,
    )

    def __init__(self, *args, **kwargs):
        super(NT4, self).__init__(*args, **kwargs)

        if self.nt4_adminpw:
            try:
                self.nt4_adminpw = notifier().pwenc_decrypt(self.nt4_adminpw)
            except:
                log.debug('Failed to decrypt NT4 admin password', exc_info=True)
                self.nt4_adminpw = ''
        self._nt4_adminpw_encrypted = False

        self.ds_type = DS_TYPE_NT4
        self.ds_name = enum_to_directoryservice(self.ds_type)

        if not self.nt4_netbiosname:
            from freenasUI.network.models import GlobalConfiguration
            gc_hostname = GlobalConfiguration.objects.all().order_by('-id')[0].get_hostname()
            if gc_hostname:
                m = re.match(r"^([a-zA-Z][a-zA-Z0-9]+)", gc_hostname)
                if m:
                    self.nt4_netbiosname = m.group(0).upper().strip()

    def save(self, *args, **kwargs):
        if self.nt4_adminpw and not self._nt4_adminpw_encrypted:
            self.nt4_adminpw = notifier().pwenc_encrypt(
                self.nt4_adminpw
            )
            self._nt4_adminpw_encrypted = True
        super(NT4, self).save(*args, **kwargs)

    class Meta:
        verbose_name = _("NT4 Domain")
        verbose_name_plural = _("NT4 Domain")


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
    ad_netbiosname_a = models.CharField(
        verbose_name=_("NetBIOS Name"),
        max_length=120,
        help_text=_("System hostname"),
        blank=True
    )
    ad_netbiosname_b = models.CharField(
        verbose_name=_("NetBIOS Name"),
        max_length=120,
        help_text=_("System hostname"),
        blank=True,
        null=True,
    )

    @property
    def ad_netbiosname(self):
        from freenasUI.services.models import CIFS
        cifs = CIFS.objects.latest('id')
        if not cifs:
            return None
        return cifs.get_netbiosname()

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
        CertificateAuthority,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    ad_verbose_logging = models.BooleanField(
        verbose_name=_("Verbose logging"),
        default=False
    )
    ad_unix_extensions = models.BooleanField(
        verbose_name=_("UNIX extensions"),
        help_text=_("Set this if your Active Directory has UNIX extensions."),
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
        help_text=_("Set this if you want to disable caching Active Directory users and groups.  Use this option if you are experiencing slowness or having difficulty binding to the domain with a large number of users and groups."),
        default=False
    )
    ad_site = models.CharField(
        verbose_name=_("Site Name"),
        max_length=120,
        help_text=_("Name of site to use."),
        blank=True,
        null=True
    )
    ad_dcname = models.CharField(
        verbose_name=_("Domain Controller"),
        max_length=120,
        help_text=_("FQDN of the domain controller to use."),
        blank=True,
        null=True
    )
    ad_gcname = models.CharField(
        verbose_name=_("Global Catalog Server"),
        max_length=120,
        help_text=_("FQDN of the global catalog server to use."),
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
    ad_kerberos_principal = models.ForeignKey(
        KerberosPrincipal,
        verbose_name=_("Kerberos Principal"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
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
        choices=choices.IDMAP_CHOICES,
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
                    "CurrentControlSet\Services\NTDS\Parameters\\"
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
            except:
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

        if not self.ad_kerberos_realm:
            from freenasUI.common.freenasldap import (
                FreeNAS_ActiveDirectory,
                FLAGS_DBINIT
            )

            try:
                FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)

                kr = KerberosRealm.objects.filter(
                    krb_realm=self.ad_domainname.upper()
                )
                if kr:
                    kr = kr[0]
                else:
                    kr = KerberosRealm()
                    kr.krb_realm = self.ad_domainname.upper()
                    kr.save()

                self.ad_kerberos_realm = kr
                super(ActiveDirectory, self).save()

            except Exception as e:
                log.debug("ActiveDirectory: Unable to create kerberos realm: %s", e)

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
    ldap_netbiosname_a = models.CharField(
        verbose_name=_("NetBIOS Name"),
        max_length=120,
        help_text=_("System hostname"),
        blank=True
    )
    ldap_netbiosname_b = models.CharField(
        verbose_name=_("NetBIOS Name"),
        max_length=120,
        help_text=_("System hostname"),
        blank=True,
        null=True,
    )

    @property
    def ldap_netbiosname(self):
        _n = notifier()
        if not _n.is_freenas():
            if _n.failover_node() == 'B':
                return self.ldap_netbiosname_b
            else:
                return self.ldap_netbiosname_a
        else:
            return self.ldap_netbiosname_a
    ldap_kerberos_realm = models.ForeignKey(
        KerberosRealm,
        verbose_name=_("Kerberos Realm"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    ldap_kerberos_principal = models.ForeignKey(
        KerberosPrincipal,
        verbose_name=_("Kerberos Principal"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
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
        CertificateAuthority,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
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
        choices=choices.IDMAP_CHOICES,
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
        help_text=_("These parameters are added to sssd.conf")
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
            except:
                log.debug('Failed to decrypt LDAP bind password', exc_info=True)
                self.ldap_bindpw = ''
        self._ldap_bindpw_encrypted = False

        self.ds_type = DS_TYPE_LDAP
        self.ds_name = enum_to_directoryservice(self.ds_type)

        if not self.ldap_netbiosname_a:
            from freenasUI.network.models import GlobalConfiguration
            gc_hostname = GlobalConfiguration.objects.all().order_by('-id')[0].get_hostname()
            if gc_hostname:
                m = re.match(r"^([a-zA-Z][a-zA-Z0-9\.\-]+)", gc_hostname)
                if m:
                    self.ldap_netbiosname_a = m.group(0).upper().strip()

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
