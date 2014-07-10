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
import logging
import re

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.freeadmin.models import Model

log = logging.getLogger("directoryservice.forms")


class NT4(Model):
    nt4_dcname = models.CharField(
        max_length=120,
        verbose_name=_("Domain Controller"),
        help_text=_("Hostname of the domain controller to use."),
    )
    nt4_netbiosname = models.CharField(
        max_length=120,
        verbose_name=_("NetBIOS Name"),
        help_text=_("System hostname"),
        blank=True
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
    nt4_use_default_domain = models.BooleanField(
        default=False,
        verbose_name=_("Use default domain"),
        help_text=_("Set this if you want to use the default domain for users and groups.")
    )
    nt4_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False,
    )


    def __init__(self, *args, **kwargs):
        super(NT4, self).__init__(*args, **kwargs)
        self.svc = 'nt4'

        if not self.nt4_netbiosname:
            from freenasUI.network.models import GlobalConfiguration
            gc_hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname
            if gc_hostname:
                m = re.match(r"^([a-zA-Z][a-zA-Z0-9]+)", gc_hostname)
                if m:
                    self.nt4_netbiosname = m.group(0).upper().strip()

    class Meta:
        verbose_name = _("NT4 Domain")
        verbose_name_plural = _("NT4 Domain")

    class FreeAdmin:
        deletable = False


class ActiveDirectory(Model):
    ad_domainname = models.CharField(
        max_length=120,
        verbose_name=_("Domain Name (DNS/Realm-Name)"),
        help_text=_("Domain Name, eg example.com")
    )
    ad_bindname = models.CharField(
        max_length=120,
        verbose_name=_("Domain Account Name"),
        help_text=_("Domain account name to bind as")
    )
    ad_bindpw = models.CharField(
        max_length=120,
        verbose_name=_("Domain Account Password"),
        help_text=_("Domain Account password.")
    )

    #
    # AD Advanced settings
    #
    ad_netbiosname = models.CharField(
        max_length=120,
        verbose_name=_("NetBIOS Name"),
        help_text=_("System hostname"),
        blank=True
    )
    ad_use_keytab = models.BooleanField(
        default=False,
        verbose_name=_("Use keytab"),
    )
    ad_keytab = models.TextField(
        verbose_name=_("Kerberos keytab"),
        help_text=_("Kerberos keytab file"),
        blank=True,
        null=True,
    )
    ad_ssl = models.CharField(
        choices=choices.LDAP_SSL_CHOICES,
        default='off',
        max_length=120,
        verbose_name=_("Encryption Mode"),
        help_text=_(
            "This parameter specifies whether to use SSL/TLS, e.g."
            " on/off/start_tls"
        )
    )
    ad_certfile = models.TextField(
        verbose_name=_("SSL Certificate"),
        blank=True,
        help_text=_("Upload your certificate file here.")
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
        default=False,
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
    ad_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False,
    )

    def __init__(self, *args, **kwargs):
        super(ActiveDirectory, self).__init__(*args, **kwargs)
        self.svc = 'activedirectory'

        if not self.ad_netbiosname:  
            from freenasUI.network.models import GlobalConfiguration
            gc_hostname = GlobalConfiguration.objects.all().order_by('-id')[0].gc_hostname
            if gc_hostname:
                m = re.match(r"^([a-zA-Z][a-zA-Z0-9\.\-]+)", gc_hostname)
                if m:
                    self.ad_netbiosname = m.group(0).upper().strip()


    class Meta:
        verbose_name = _("Active Directory")
        verbose_name_plural = _("Active Directory")

    class FreeAdmin:
        deletable = False
        icon_model = "ActiveDirectoryIcon"
        advanced_fields = (
            'ad_netbiosname',
            'ad_use_keytab',
            'ad_keytab',
            'ad_ssl',
            'ad_certfile',
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


class NIS(Model):
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
    nis_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False,
    )

    def __init__(self, *args, **kwargs):
        super(NIS, self).__init__(*args, **kwargs)
        self.svc = 'nis'

    class Meta:
        verbose_name = _("NIS Domain")
        verbose_name_plural = _("NIS Domain")

    class FreeAdmin:
        deletable = False


class LDAP(Model):
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
    ldap_binddn = models.CharField(
        max_length=120,
        verbose_name=_("Bind DN"),
        blank=True,
        help_text=_("The distinguished name with which to bind to the "
            "directory server, e.g. cn=admin,dc=test,dc=org")
    )
    ldap_bindpw = models.CharField(
        max_length=120,
        verbose_name=_("Bind password"),
        blank=True,
        help_text=_("The credentials with which to bind.")
    )
    ldap_anonbind = models.BooleanField(
        verbose_name=_("Allow Anonymous Binding"),
        default=False,
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
    ldap_use_default_domain = models.BooleanField(
        default=False,
        verbose_name=_("Use default domain"),
        help_text=_("Set this if you want to use the default domain for users and groups.")
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
    ldap_certfile = models.TextField(
        verbose_name=_("SSL Certificate"),
        blank=True,
        help_text=_("Upload your certificate file here.")
    )
    ldap_enable = models.BooleanField(
        verbose_name=_("Enable"),
        default=False,
    )

    def __init__(self, *args, **kwargs):
        super(LDAP, self).__init__(*args, **kwargs)
        self.svc = 'ldap'

    class Meta:
        verbose_name = _("LDAP")
        verbose_name_plural = _("LDAP")

    class FreeAdmin:
        deletable = False
        icon_model = "LDAPIcon"
        advanced_fields = (
            'ldap_anonbind',
            'ldap_usersuffix',
            'ldap_groupsuffix',
            'ldap_passwordsuffix',
            'ldap_machinesuffix',
            'ldap_ssl',
            'ldap_use_default_domain',
            'ldap_certfile',
        )
