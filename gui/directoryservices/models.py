#+
# Copyright 2013 iXsystems, Inc.
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
from freenasUI.freeadmin.models import Model

log = logging.getLogger("directoryservices.models")

class DirectoryServiceBase(Model):
    ds_type = models.CharField(
        max_length=120,
        verbose_name=_("Type")
    )
    ds_name = models.CharField(
        max_length=120,
        verbose_name=_("Name")
    )
    ds_enable = models.BooleanField(
        default=False,
        verbose_name=_("Enable")
    ) 

    class Meta:
        abstract = True


class NT4(DirectoryServiceBase):
    nt4_dcname = models.CharField(
        max_length=120,
        verbose_name=_("Domain Controller"),
        help_text=_("Hostname of the domain controller to use."),
    )
    nt4_netbiosname = models.CharField(
        max_length=120,
        verbose_name=_("NetBIOS Name"),
        help_text=_("System hostname")
    )
    nt4_workgroup = models.CharField(
        max_length=120,
        verbose_name=_("Workgroup Name"),
        help_text=_("Workgroup or domain name in old format, eg WORKGROUP")
    )
    nt4_adminname = models.CharField(
        max_length=120,
        verbose_name=_("Administrator Name"),
        help_text=_("Domain Administrator account name")
    )
    nt4_adminpw = models.CharField(
        max_length=120,
        verbose_name=_("Administrator Password"),
        help_text=_("Domain Administrator account password.")
    )

    def __init__(self, *args, **kwargs):
        super(NT4, self).__init__(*args, **kwargs)
        self.ds_type = 'NT4'

    class Meta:
        verbose_name = _("NT4 Domain")
        verbose_name_plural = _("NT4 Domain")

    class FreeAdmin:
        deletable = False


class ActiveDirectory(DirectoryServiceBase):
    ad_domainname = models.CharField(
        max_length=120,
        verbose_name=_("Domain Name (DNS/Realm-Name)"),
        help_text=_("Domain Name, eg example.com")
    )
    ad_netbiosname = models.CharField(
        max_length=120,
        verbose_name=_("NetBIOS Name"),
        help_text=_("System hostname")
    )
    ad_workgroup = models.CharField(
        max_length=120,
        verbose_name=_("Workgroup Name"),
        help_text=_("Workgroup or domain name in old format, eg WORKGROUP")
    )
    ad_adminname = models.CharField(
        max_length=120,
        verbose_name=_("Administrator Name"),
        help_text=_("Domain Administrator account name")
    )
    ad_adminpw = models.CharField(
        max_length=120,
        verbose_name=_("Administrator Password"),
        help_text=_("Domain Administrator account password.")
    )
    ad_verbose_logging = models.BooleanField(
        default=False,
        verbose_name=_("Verbose logging"),
    )
    ad_unix_extensions = models.BooleanField(
        default=False,
        verbose_name=_("UNIX extensions"),
        help_text=_("Set this if your Active Directory has UNIX extensions.")
    )
    ad_allow_trusted_doms = models.BooleanField(
        default=False,
        verbose_name=_("Allow Trusted Domains"),
        help_text=_("Set this if you want to allow Trusted Domains.")
    )
    ad_use_default_domain = models.BooleanField(
        default=True,
        verbose_name=_("Use default domain"),
        help_text=_("Set this if you want to use the default domain for users and groups.")
    )
    ad_dcname = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Domain Controller"),
        help_text=_("Hostname of the domain controller to use."),
    )
    ad_gcname = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Global Catalog Server"),
        help_text=_("Hostname of the global catalog server to use."),
    )
    ad_krbname = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Kerberos Server"),
        help_text=_("Hostname of the kerberos server to use."),
    )
    ad_kpwdname = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Kerberos Password Server"),
        help_text=_("Hostname of the kerberos password server to use."),
    )
    ad_timeout = models.IntegerField(
        default=10,
        verbose_name=_("AD timeout"),
        help_text=_("Timeout for AD related commands."),
    )
    ad_dns_timeout = models.IntegerField(
        default=10,
        verbose_name=_("DNS timeout"),
        help_text=_("Timeout for AD DNS queries."),
    )

    def __init__(self, *args, **kwargs):
        super(ActiveDirectory, self).__init__(*args, **kwargs)
        self.ds_type = 'ActiveDirectory'

    class Meta:
        verbose_name = _("Active Directory")
        verbose_name_plural = _("Active Directory")

    class FreeAdmin:
        deletable = False
        icon_model = "ActiveDirectoryIcon"
        advanced_fields = (
            'ad_verbose_logging',
            'ad_unix_extensions',
            'ad_allow_trusted_doms',
            'ad_use_default_domain',
            'ad_dcname',
            'ad_gcname',
            'ad_krbname',
            'ad_kpwdname',
            'ad_timeout',
            'ad_dns_timeout'
        )


class NIS(DirectoryServiceBase):
    nis_domain = models.CharField(
        max_length=120,
        verbose_name=_("NIS domain"),
        help_text=_("NIS domain name")
    )
    nis_servers = models.CharField(
        blank=True,
        max_length=8192,
        verbose_name=_("NIS servers"),
        help_text=_("Comma delimited list of NIS servers")
    )
    nis_secure_mode = models.BooleanField(
        default=False,
        verbose_name=_("Secure mode"),
        help_text=_("Cause ypbind to run in secure mode")
    )
    nis_manycast = models.BooleanField(
        default=False,
        verbose_name=_("Manycast"),
        help_text=_("Cause ypbind to use 'many-cast' instead of broadcast")
    )

    def __init__(self, *args, **kwargs):
        super(NIS, self).__init__(*args, **kwargs)
        self.ds_type = 'NIS'

    class Meta:
        verbose_name = _("NIS Domain")
        verbose_name_plural = _("NIS Domain")

    class FreeAdmin:
        deletable = False


class LDAP(DirectoryServiceBase):
    ldap_hostname = models.CharField(
        max_length=120,
        verbose_name=_("Hostname"),
        blank=True,
        help_text=_("The name or IP address of the LDAP server")
    )
    ldap_basedn = models.CharField(
        max_length=120,
        verbose_name=_("Base DN"),
        blank=True,
        help_text=_("The default base Distinguished Name (DN) to use for "
            "searches, eg dc=test,dc=org")
    )
    ldap_anonbind = models.BooleanField(
        verbose_name=_("Allow Anonymous Binding"))
    ldap_rootbasedn = models.CharField(
        max_length=120,
        verbose_name=_("Root bind DN"),
        blank=True,
        help_text=_("The distinguished name with which to bind to the "
            "directory server, e.g. cn=admin,dc=test,dc=org")
    )
    ldap_rootbindpw = models.CharField(
        max_length=120,
        verbose_name=_("Root bind password"),
        blank=True,
        help_text=_("The credentials with which to bind.")
    )
    ldap_pwencryption = models.CharField(
        max_length=120,
        choices=choices.PWEncryptionChoices,
        default='clear',
        verbose_name=_("Password Encryption"),
        help_text=_("The password change protocol to use.")
    )
    ldap_usersuffix = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("User Suffix"),
        help_text=_("This parameter specifies the suffix that is used for "
            "users when these are added to the LDAP directory, e.g. "
            "ou=Users")
    )
    ldap_groupsuffix = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Group Suffix"),
        help_text=_("This parameter specifies the suffix that is used "
            "for groups when these are added to the LDAP directory, e.g. "
            "ou=Groups")
    )
    ldap_passwordsuffix = models.CharField(
        max_length=120,
        verbose_name=_("Password Suffix"),
        blank=True,
        help_text=_("This parameter specifies the suffix that is used for "
            "passwords when these are added to the LDAP directory, e.g. "
            "ou=Passwords")
    )
    ldap_machinesuffix = models.CharField(
        max_length=120,
        verbose_name=_("Machine Suffix"),
        blank=True,
        help_text=_("This parameter specifies the suffix that is used for "
            "machines when these are added to the LDAP directory, e.g. "
            "ou=Computers")
    )
    ldap_ssl = models.CharField(
        choices=choices.LDAP_SSL_CHOICES,
        default='off',
        max_length=120,
        verbose_name=_("Encryption Mode"),
        help_text=_(
            "This parameter specifies whether to use SSL/TLS, e.g."
            " on/off/start_tls"
        )
    )
    ldap_tls_cacertfile = models.TextField(
        verbose_name=_("Self signed certificate"),
        blank=True,
        help_text=_("Place the contents of your self signed certificate "
            "file here.")
    )
    ldap_options = models.TextField(
        max_length=120,
        verbose_name=_("Auxiliary Parameters"),
        blank=True,
        help_text=_("These parameters are added to ldap.conf.")
    )

    def __init__(self, *args, **kwargs):
        super(LDAP, self).__init__(*args, **kwargs)
        self.ds_type = 'LDAP'

    class Meta:
        verbose_name = _("LDAP")
        verbose_name_plural = _("LDAP")

    class FreeAdmin:
        deletable = False
        icon_model = "LDAPIcon"
