# +
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
import hashlib
import hmac
import logging
import uuid

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.validators import (
    MinValueValidator, MaxValueValidator
)

from freenasUI import choices
from freenasUI.directoryservice.models import (
    KerberosRealm,
)
from freenasUI.freeadmin.models import (
    Model, UserField, GroupField, PathField,
    ConfigQuerySet, NewModel, NewManager, ListField
)
from freenasUI.freeadmin.models.fields import MultiSelectField
from freenasUI.middleware.notifier import notifier
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.storage.models import Disk
from freenasUI.system.models import Certificate

log = logging.getLogger("services.forms")


class services(Model):
    srv_service = models.CharField(
        max_length=120,
        verbose_name=_("Service"),
        help_text=_("Name of Service, should be auto-generated at build "
                    "time"),
    )
    srv_enable = models.BooleanField(
        verbose_name=_("Enable Service"),
        default=False,
    )

    class Meta:
        verbose_name = _("Services")
        verbose_name_plural = _("Services")

    def __unicode__(self):
        return self.srv_service

    def save(self, *args, **kwargs):
        super(services, self).save(*args, **kwargs)


class CIFS(NewModel):
    cifs_srv_netbiosname = models.CharField(
        max_length=120,
        verbose_name=_("NetBIOS name"),
    )
    cifs_srv_workgroup = models.CharField(
        max_length=120,
        verbose_name=_("Workgroup"),
        help_text=_("Workgroup the server will appear to be in when "
                    "queried by clients (maximum 15 characters)."),
    )
    cifs_srv_description = models.CharField(
        max_length=120,
        verbose_name=_("Description"),
        blank=True,
        help_text=_("Server description. This can usually be left blank."),
    )
    cifs_srv_doscharset = models.CharField(
        max_length=120,
        choices=choices.DOSCHARSET_CHOICES,
        default="CP437",
        verbose_name=_("DOS charset"),
    )
    cifs_srv_unixcharset = models.CharField(
        max_length=120,
        choices=choices.UNIXCHARSET_CHOICES,
        default="UTF-8",
        verbose_name=_("UNIX charset"),
    )
    cifs_srv_loglevel = models.CharField(
        max_length=120,
        choices=choices.LOGLEVEL_CHOICES,
        default=choices.LOGLEVEL_CHOICES[0][0],
        verbose_name=_("Log level"),
    )
    cifs_srv_syslog = models.BooleanField(
        verbose_name=_("Use syslog"),
        default=False,
    )
    cifs_srv_localmaster = models.BooleanField(
        verbose_name=_("Local Master"),
        default=False,
    )
    cifs_srv_domain_logons = models.BooleanField(
        verbose_name=_("Domain logons"),
        default=False,
    )
    cifs_srv_timeserver = models.BooleanField(
        verbose_name=_("Time Server for Domain"),
        default=False,
    )
    cifs_srv_guest = UserField(
        max_length=120,
        default="nobody",
        exclude=["root"],
        verbose_name=_("Guest account"),
        help_text=_("Use this option to override the username "
                    "('nobody' by default) which will be used for "
                    "access to services which are specified as guest. "
                    "Whatever privileges this user has will be "
                    "available to any client connecting to the guest "
                    "service. This user must exist in the password file, "
                    "but does not require a valid login. The user root can "
                    "not be used as guest account."),
        )
    cifs_srv_filemask = models.CharField(
        max_length=120,
        verbose_name=_("File mask"),
        blank=True,
        help_text=_("Use this option to override the file creation mask "
                    "(0666 by default)."),
    )
    cifs_srv_dirmask = models.CharField(
        max_length=120,
        verbose_name=_("Directory mask"),
        blank=True,
        help_text=_("Use this option to override the directory creation "
                    "mask (0777 by default)."),
    )
    cifs_srv_nullpw = models.BooleanField(
        verbose_name=_("Allow Empty Password"),
        default=False,
    )
    cifs_srv_smb_options = models.TextField(
        verbose_name=_("Auxiliary parameters"),
        blank=True,
        help_text=_("These parameters are added to [global] section of "
                    "smb.conf"),
    )
    cifs_srv_unixext = models.BooleanField(
        verbose_name=_("Unix Extensions"),
        default=True,
        help_text=_("These extensions enable Samba to better serve UNIX "
                    "CIFS clients by supporting features such as symbolic "
                    "links, hard links, etc..."),
    )
    cifs_srv_aio_enable = models.BooleanField(
        default=False,
        verbose_name=_("Enable AIO"),
        editable=False,
        help_text=_("Enable/disable AIO support."),
    )
    cifs_srv_aio_rs = models.IntegerField(
        max_length=120,
        verbose_name=_("Minimum AIO read size"),
        help_text=_("Samba will read asynchronously if request size is "
                    "larger than this value."),
        default=4096,
        editable=False,
    )
    cifs_srv_aio_ws = models.IntegerField(
        max_length=120,
        verbose_name=_("Minimum AIO write size"),
        help_text=_("Samba will write asynchronously if request size is "
                    "larger than this value."),
        default=4096,
        editable=False,
    )
    cifs_srv_zeroconf = models.BooleanField(
        verbose_name=_("Zeroconf share discovery"),
        default=True,
        help_text=_("Zeroconf support via Avahi allows clients (the Mac "
                    "OSX finder in particular) to automatically discover the "
                    "CIFS shares on the system similar to the Computer "
                    "Browser service in Windows."),
    )
    cifs_srv_hostlookup = models.BooleanField(
        verbose_name=_("Hostnames lookups"),
        default=True,
        help_text=_("Specifies whether samba should use (expensive) "
                    "hostname lookups or use the ip addresses instead. An "
                    "example place where hostname lookups are currently used "
                    "is when checking the hosts deny and hosts allow."),
    )
    cifs_srv_min_protocol = models.CharField(
        max_length=120,
        verbose_name=_("Server minimum protocol"),
        choices=choices.CIFS_SMB_PROTO_CHOICES,
        help_text=_("The minimum protocol version that will be supported by "
                    "the server"),
        blank=True,
    )
    cifs_srv_max_protocol = models.CharField(
        max_length=120,
        verbose_name=_("Server maximum protocol"),
        default='SMB2',
        choices=choices.CIFS_SMB_PROTO_CHOICES,
        help_text=_("The highest protocol version that will be supported by "
                    "the server"),
    )
    cifs_srv_allow_execute_always = models.BooleanField(
        verbose_name=_("Allow execute always"),
        default=True,
        help_text=_("This boolean parameter controls the behaviour of smbd(8) "
                    "when receiving a protocol request of \"open for "
                    "execution\" from a Windows " "client. With Samba 3.6 and "
                    "older, the execution right in the ACL was not checked, "
                    "so a client could execute a file even if it did not have "
                    "execute rights on the file. In Samba 4.0, this has been "
                    "fixed, so that by default, i.e. when this parameter is "
                    "set to " "\"False\", \"open for execution\" is now "
                    "denied when execution " "permissions are not present. If "
                    "this parameter is set to \"True\", Samba does not check "
                    "execute permissions on \"open for execution\", thus "
                    "re-establishing the behaviour of Samba 3.6 "),
    )
    cifs_srv_obey_pam_restrictions = models.BooleanField(
        verbose_name=_("Obey pam restrictions"),
        default=True,
        help_text=_("This parameter controls whether or not Samba should obey "
                    "PAM's account and session management directives"),
    )
    cifs_srv_bindip = MultiSelectField(
        verbose_name=_("Bind IP Addresses"),
        help_text=_("IP address(es) to bind to. If none specified, all "
                    "available interfaces that are up will be listened on."),
        max_length=250,
        blank=True,
        null=True,
    )
    cifs_SID = models.CharField(
        max_length=120,
        blank=True,
        null=True,
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _(u"CIFS")
        verbose_name_plural = _(u"CIFS")

    class FreeAdmin:
        deletable = False
        icon_model = u"CIFSIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('cifs_srv_netbiosname', 'netbiosname'),
            ('cifs_srv_workgroup', 'workgroup'),
            ('cifs_srv_description', 'description'),
            ('cifs_srv_doscharset', 'dos_charset'),
            ('cifs_srv_unixcharset', 'unix_charset'),
            ('cifs_srv_loglevel', 'log_level'),
            ('cifs_srv_syslog', 'syslog'),
            ('cifs_srv_localmaster', 'local_master'),
            ('cifs_srv_domain_logons', 'domain_logons'),
            ('cifs_srv_timeserver', 'time_server'),
            ('cifs_srv_guest', 'guest_user'),
            ('cifs_srv_filemask', 'filemask'),
            ('cifs_srv_dirmask', 'dirmask'),
            ('cifs_srv_nullpw', 'empty_password'),
            ('cifs_srv_unixext', 'unixext'),
            ('cifs_srv_zeroconf', 'zeroconf'),
            ('cifs_srv_hostlookup', 'hostlookup'),
            ('cifs_srv_min_protocol', 'min_protocol'),
            ('cifs_srv_max_protocol', 'max_protocol'),
            ('cifs_srv_allow_execute_always', 'execute_always'),
            ('cifs_srv_obey_pam_restrictions', 'obey_pam_restrictions'),
            ('cifs_srv_bindip', 'bind_addresses'),
            ('cifs_SID', 'sid'),
            ('cifs_srv_smb_options', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.cifs.get_config')
        return cls(**dict(
            id=1,
            cifs_srv_netbiosname=' '.join(config['netbiosname']),
            cifs_srv_workgroup=config['workgroup'],
            cifs_srv_description=config['description'],
            cifs_srv_doscharset=config['dos_charset'],
            cifs_srv_unixcharset=config['unix_charset'],
            cifs_srv_loglevel=config['log_level'],
            cifs_srv_syslog=config['syslog'],
            cifs_srv_localmaster=config['local_master'],
            cifs_srv_domain_logons=config['domain_logons'],
            cifs_srv_timeserver=config['time_server'],
            cifs_srv_guest=config['guest_user'],
            cifs_srv_filemask=config['filemask'],
            cifs_srv_dirmask=config['dirmask'],
            cifs_srv_nullpw=config['empty_password'],
            cifs_srv_unixext=config['unixext'],
            cifs_srv_zeroconf=config['zeroconf'],
            cifs_srv_hostlookup=config['hostlookup'],
            cifs_srv_min_protocol=config['min_protocol'],
            cifs_srv_max_protocol=config['max_protocol'],
            cifs_srv_allow_execute_always=config['execute_always'],
            cifs_srv_obey_pam_restrictions=config['obey_pam_restrictions'],
            cifs_srv_bindip=config['bind_addresses'],
            cifs_SID=config['sid'],
            cifs_srv_smb_options=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'netbiosname': self.cifs_srv_netbiosname.split(),
            'workgroup': self.cifs_srv_workgroup,
            'description': self.cifs_srv_description,
            'dos_charset': self.cifs_srv_doscharset,
            'unix_charset': self.cifs_srv_unixcharset,
            'log_level': self.cifs_srv_loglevel,
            'syslog': self.cifs_srv_syslog,
            'local_master': self.cifs_srv_localmaster,
            'domain_logons': self.cifs_srv_domain_logons,
            'time_server': self.cifs_srv_timeserver,
            'guest_user': self.cifs_srv_guest,
            'filemask': self.cifs_srv_filemask,
            'dirmask': self.cifs_srv_dirmask,
            'empty_password': self.cifs_srv_nullpw,
            'unixext': self.cifs_srv_unixext,
            'zeroconf': self.cifs_srv_zeroconf,
            'hostlookup': self.cifs_srv_hostlookup,
            'min_protocol': self.cifs_srv_min_protocol or None,
            'max_protocol': self.cifs_srv_max_protocol,
            'execute_always': self.cifs_srv_allow_execute_always,
            'obey_pam_restrictions': self.cifs_srv_obey_pam_restrictions,
            'bind_addresses': self.cifs_srv_bindip or None,
            'sid': self.cifs_SID,
            'auxiliary': self.cifs_srv_smb_options or None,
        }
        self._save_task_call('service.cifs.configure', data)
        return True


class AFP(NewModel):
    afp_srv_guest = models.BooleanField(
        verbose_name=_("Guest Access"),
        help_text=_("Allows guest access to all apple shares on this box."),
        default=False,
    )
    afp_srv_guest_user = UserField(
        max_length=120,
        default="nobody",
        exclude=["root"],
        verbose_name=_("Guest account"),
        help_text=_("Use this option to override the username ('nobody' by "
                    "default) which will be used for access to services which "
                    "are specified as guest. Whatever privileges this user "
                    "has will be available to any client connecting to the "
                    "guest service. This user must exist in the password "
                    "file, but does not require a valid login. The user root "
                    "can not be used as guest account."),
    )
    afp_srv_bindip = ListField(
        verbose_name=_("Bind IP Addresses"),
        help_text=_(
            "IP address(es) to advertise and listens to. If none specified, "
            "advertise the first IP address of the system, but to listen for "
            "any incoming request."
        ),
        max_length=255,
        blank=True,
        choices=list(choices.IPChoices()),
        default='',
    )
    afp_srv_connections_limit = models.IntegerField(
        max_length=120,
        verbose_name=_('Max. Connections'),
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text=_("Maximum number of connections permitted via AFP. The "
                    "default limit is 50."),
        default=50,
    )
    afp_srv_homedir_enable = models.BooleanField(
        verbose_name=_("Enable home directories"),
        help_text=_("Enable/disable home directories for afp user."),
        default=False,
    )
    afp_srv_homedir = PathField(
        verbose_name=_("Home directories"),
        blank=True,
        )
    afp_srv_homename = models.CharField(
        verbose_name=_("Home share name"),
        blank=True,
        help_text=_("When set overrides the default Home Share Name."),
        max_length=50,
    )
    afp_srv_dbpath = PathField(
        verbose_name=_('Database Path'),
        blank=True,
        help_text=_(
            'Sets the database information to be stored in path. You have to '
            'specify a writable location, even if the volume is read only.'),
    )
    afp_srv_global_aux = models.TextField(
        verbose_name=_("Global auxiliary parameters"),
        blank=True,
        null=True,
        help_text=_(
            "These parameters are added to [Global] section of afp.conf"),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _(u"AFP")
        verbose_name_plural = _(u"AFP")

    class FreeAdmin:
        deletable = False
        icon_model = u"AFPIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('afp_srv_guest', 'guest_enable'),
            ('afp_srv_guest_user', 'guest_user'),
            ('afp_srv_bindip', 'bind_addresses'),
            ('afp_srv_connections_limit', 'connections_limit'),
            ('afp_srv_homedir_enable', 'homedir_enable'),
            ('afp_srv_homedir', 'homedir_path'),
            ('afp_srv_homename', 'homedir_name'),
            ('afp_srv_dbpath', 'dbpath'),
            ('afp_srv_global_aux', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.afp.get_config')
        return cls(**dict(
            id=1,
            afp_srv_guest=config['guest_enable'],
            afp_srv_guest_user=config['guest_user'],
            afp_srv_bindip=config['bind_addresses'],
            afp_srv_connections_limit=config['connections_limit'],
            afp_srv_homedir_enable=config['homedir_enable'],
            afp_srv_homedir=config['homedir_path'],
            afp_srv_homename=config['homedir_name'],
            afp_srv_dbpath=config['dbpath'],
            afp_srv_global_aux=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'guest_enable': self.afp_srv_guest,
            'guest_user': self.afp_srv_guest_user,
            'bind_addresses': self.afp_srv_bindip or None,
            'connections_limit': self.afp_srv_connections_limit,
            'homedir_enable': self.afp_srv_homedir_enable,
            'homedir_path': self.afp_srv_homedir or None,
            'homedir_name': self.afp_srv_homename or None,
            'dbpath': self.afp_srv_dbpath or None,
            'auxiliary': self.afp_srv_global_aux or None,
        }
        self._save_task_call('service.afp.configure', data)
        return True


class NFS(NewModel):
    nfs_srv_servers = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(256)],
        verbose_name=_("Number of servers"),
        help_text=_("Specifies how many servers to create. There should be "
                    "enough to handle the maximum level of concurrency from "
                    "its clients, typically four to six."),
    )
    nfs_srv_udp = models.BooleanField(
        verbose_name=_('Serve UDP NFS clients'),
        default=False,
    )
    nfs_srv_allow_nonroot = models.BooleanField(
        default=False,
        verbose_name=_("Allow non-root mount"),
        help_text=_("Allow non-root mount requests to be served. This should "
                    "only be specified if there are clients that require it. "
                    "It will automatically clear the vfs.nfsrv.nfs_privport "
                    "sysctl flag, which controls if the kernel will accept "
                    "NFS requests from reserved ports only."),
    )
    nfs_srv_v4 = models.BooleanField(
        default=False,
        verbose_name=_("Enable NFSv4"),
    )
    nfs_srv_v4_krb = models.BooleanField(
        default=False,
        verbose_name=_("Require Kerberos for NFSv4"),
    )
    nfs_srv_bindip = models.CharField(
        blank=True,
        max_length=250,
        verbose_name=_("Bind IP Addresses"),
        help_text=_("Specify specific IP addresses (separated by commas) to "
                    "bind to for TCP and UDP requests. This option may be "
                    "specified multiple times. If no IP is specified it will "
                    "bind to INADDR_ANY. It will automatically add 127.0.0.1 "
                    "and if IPv6 is enabled, ::1 to the list."),
    )
    nfs_srv_mountd_port = models.SmallIntegerField(
        verbose_name=_("mountd(8) bind port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        blank=True,
        null=True,
        help_text=_(
            "Force mountd to bind to the specified port, for both IPv4 and "
            "IPv6 address families. This is typically done to ensure that "
            "the port which mountd binds to is a known value which can be "
            "used in firewall rulesets."),
    )
    nfs_srv_rpcstatd_port = models.SmallIntegerField(
        verbose_name=_("rpc.statd(8) bind port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        blank=True,
        null=True,
        help_text=_(
            "This option forces the rpc.statd daemon to bind to the specified "
            "port, for both IPv4 and IPv6 address families."),
    )
    nfs_srv_rpclockd_port = models.SmallIntegerField(
        verbose_name=_("rpc.lockd(8) bind port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        blank=True,
        null=True,
        help_text=_(
            "This option forces rpc.lockd the daemon to bind to the specified "
            "port, for both IPv4 and IPv6 address families."),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("NFS")
        verbose_name_plural = _("NFS")

    class Middleware:
        configstore = True
        field_mapping = (
            ('nfs_srv_servers', 'servers'),
            ('nfs_srv_udp', 'udp'),
            ('nfs_srv_allow_nonroot', 'nonroot'),
            ('nfs_srv_v4', 'v4'),
            ('nfs_srv_v4_krb', 'v4_kerberos'),
            ('nfs_srv_bindip', 'bind_addresses'),
            ('nfs_srv_mountd_port', 'mountd_port'),
            ('nfs_srv_rpcstatd_port', 'rpcstatd_port'),
            ('nfs_srv_rpclockd_port', 'rpclockd_port'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.nfs.get_config')
        return cls(**dict(
            id=1,
            nfs_srv_servers=config['servers'],
            nfs_srv_udp=config['udp'],
            nfs_srv_allow_nonroot=config['nonroot'],
            nfs_srv_v4=config['v4'],
            nfs_srv_v4_krb=config['v4_kerberos'],
            nfs_srv_bindip=','.join(config['bind_addresses'] or []) or None,
            nfs_srv_mountd_port=config['mountd_port'],
            nfs_srv_rpcstatd_port=config['rpcstatd_port'],
            nfs_srv_rpclockd_port=config['rpclockd_port'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'servers': self.nfs_srv_servers,
            'udp': self.nfs_srv_udp,
            'nonroot': self.nfs_srv_allow_nonroot,
            'v4': self.nfs_srv_v4,
            'v4_kerberos': self.nfs_srv_v4_krb,
            'bind_addresses': self.nfs_srv_bindip.split(',') or None,
            'mountd_port': self.nfs_srv_mountd_port,
            'rpcstatd_port': self.nfs_srv_rpcstatd_port,
            'rpclockd_port': self.nfs_srv_rpclockd_port,
        }
        self._save_task_call('service.nfs.configure', data)
        return True


class iSCSITargetGlobalConfiguration(Model):
    iscsi_basename = models.CharField(
        max_length=120,
        verbose_name=_("Base Name"),
        help_text=_("The base name (e.g. iqn.2005-10.org.freenas.ctl, "
                    "see RFC 3720 and 3721 for details) will append the "
                    "target " "name that is not starting with 'iqn.', "
                    "'eui.' or 'naa.'"),
    )
    iscsi_isns_servers = models.TextField(
        verbose_name=_('iSNS Servers'),
        blank=True,
        help_text=_("List of Internet Storage Name Service (iSNS) Servers"),
    )
    iscsi_pool_avail_threshold = models.IntegerField(
        verbose_name=_('Pool Available Space Threshold (%)'),
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        help_text=_(
            "Remaining ZFS pool capacity warning threshold when using zvol "
            "extents"
        ),
    )

    class Meta:
        verbose_name = _(u"Target Global Configuration")
        verbose_name_plural = _(u"Target Global Configuration")

    class FreeAdmin:
        deletable = False
        menu_child_of = "sharing.ISCSI"
        icon_model = u"SettingsIcon"
        nav_extra = {'type': 'iscsi', 'order': -10}
        resource_name = 'services/iscsi/globalconfiguration'


class iSCSITargetExtent(Model):
    iscsi_target_extent_name = models.CharField(
        max_length=120,
        unique=True,
        verbose_name=_("Extent Name"),
        help_text=_("String identifier of the extent."),
    )
    iscsi_target_extent_serial = models.CharField(
        verbose_name=_("Serial"),
        max_length=16,
        default="10000001",
        help_text=_("Serial number for the logical unit")
    )
    iscsi_target_extent_type = models.CharField(
        max_length=120,
        verbose_name=_("Extent Type"),
        help_text=_("Type used as extent."),
    )
    iscsi_target_extent_path = models.CharField(
        max_length=120,
        verbose_name=_("Path to the extent"),
        help_text=_("File path (e.g. /mnt/sharename/extent/extent0) "
                    "used as extent."),
    )
    iscsi_target_extent_filesize = models.CharField(
        max_length=120,
        default=0,
        verbose_name=_("Extent size"),
        help_text=_("Size of extent, 0 means auto, a raw number is bytes"
                    ", or suffix with KB, MB, TB for convenience."),
    )
    iscsi_target_extent_blocksize = models.IntegerField(
        max_length=4,
        choices=choices.TARGET_BLOCKSIZE_CHOICES,
        default=choices.TARGET_BLOCKSIZE_CHOICES[0][0],
        verbose_name=_("Logical Block Size"),
        help_text=_("You may specify logical block length (512 by "
                    "default). The recommended length for compatibility is "
                    "512."),
    )
    iscsi_target_extent_pblocksize = models.BooleanField(
        default=False,
        verbose_name=_("Disable Physical Block Size Reporting"),
        help_text=_(
            'By default the physical blocksize is reported as the ZFS block '
            'size, which can be up to 128K. Some initiators do not work with '
            'values above 4K, checking this disables reporting the physical '
            'blocksize.'),
    )
    iscsi_target_extent_avail_threshold = models.IntegerField(
        verbose_name=_('Available Space Threshold (%)'),
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        help_text=_("Remaining dataset/zvol capacity warning threshold"),
    )
    iscsi_target_extent_comment = models.CharField(
        blank=True,
        max_length=120,
        verbose_name=_("Comment"),
        help_text=_("You may enter a description here for your "
                    "reference."),
    )
    iscsi_target_extent_naa = models.CharField(
        blank=True,
        editable=False,
        unique=True,
        max_length=34,
        verbose_name=_("NAA...used only by the initiator"),
    )
    iscsi_target_extent_insecure_tpc = models.BooleanField(
        default=True,
        verbose_name=_("Enable TPC"),
        help_text=_("Allow initiators to xcopy without authenticating to "
                    "foreign targets."),
    )
    iscsi_target_extent_xen = models.BooleanField(
        default=False,
        verbose_name=_("Xen initiator compat mode"),
        help_text=_("Xen inititors give errors when connecting to LUNs using "
                    "the FreeNAS default naming scheme.  Checking this alters "
                    "the naming scheme to be more Xen-friendly"),
    )
    iscsi_target_extent_rpm = models.CharField(
        blank=False,
        max_length=20,
        default=choices.EXTENT_RPM_CHOICES[1][1],
        choices=choices.EXTENT_RPM_CHOICES,
        verbose_name=_("LUN RPM"),
        help_text=_("RPM reported to initiators for this extent/LUN. The "
                    "default is SSD because windows will attempt to defrag "
                    "non SSD devices.  This is a pathological worst-case "
                    "situation for ZFS.  VMWare will give you the option to "
                    "use SSD " "LUNs as swap devices, there is some value to "
                    "picking a non-SSD RPM if your " "extent is indeed not "
                    "SSDs and the initiator will be VMWare."),
    )

    class Meta:
        verbose_name = _("Extent")
        verbose_name_plural = _("Extents")
        ordering = ["iscsi_target_extent_name"]

    def __unicode__(self):
        return unicode(self.iscsi_target_extent_name)

    def get_device(self):
        if self.iscsi_target_extent_type not in ("Disk", "ZVOL"):
            return self.iscsi_target_extent_path
        else:
            try:
                disk = Disk.objects.get(id=self.iscsi_target_extent_path)
                if disk.disk_multipath_name:
                    return "/dev/%s" % disk.devname
                else:
                    return "/dev/%s" % (
                        notifier().identifier_to_device(disk.disk_identifier),
                        )
            except:
                return self.iscsi_target_extent_path

    def delete(self):
        if self.iscsi_target_extent_type in ("Disk", "ZVOL"):
            try:
                if self.iscsi_target_extent_type == "Disk":
                    disk = Disk.objects.get(id=self.iscsi_target_extent_path)
                    devname = disk.identifier_to_device()
                    if not devname:
                        disk.disk_enabled = False
                        disk.save()
            except Exception, e:
                log.error("Unable to sync iSCSI extent delete: %s", e)

        for te in iSCSITargetToExtent.objects.filter(iscsi_extent=self):
            te.delete()
        super(iSCSITargetExtent, self).delete()

    def save(self, *args, **kwargs):
        if not self.iscsi_target_extent_naa:
            self.iscsi_target_extent_naa = '0x6589cfc000000%s' % (
                hashlib.sha256(str(uuid.uuid4())).hexdigest()[0:19]
            )
        return super(iSCSITargetExtent, self).save(*args, **kwargs)


class iSCSITargetPortal(Model):
    iscsi_target_portal_tag = models.IntegerField(
        max_length=120,
        default=1,
        verbose_name=_("Portal Group ID"),
    )
    iscsi_target_portal_comment = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Comment"),
        help_text=_("You may enter a description here for your reference."),
    )
    iscsi_target_portal_discoveryauthmethod = models.CharField(
        max_length=120,
        choices=choices.AUTHMETHOD_CHOICES,
        default='None',
        verbose_name=_("Discovery Auth Method")
    )
    iscsi_target_portal_discoveryauthgroup = models.IntegerField(
        max_length=120,
        verbose_name=_("Discovery Auth Group"),
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Portal")
        verbose_name_plural = _("Portals")

    def __unicode__(self):
        if self.iscsi_target_portal_comment != "":
            return u"%s (%s)" % (
                self.iscsi_target_portal_tag,
                self.iscsi_target_portal_comment,
                )
        else:
            return unicode(self.iscsi_target_portal_tag)

    def delete(self):
        super(iSCSITargetPortal, self).delete()
        portals = iSCSITargetPortal.objects.all().order_by(
            'iscsi_target_portal_tag')
        for portal, idx in zip(portals, xrange(1, len(portals) + 1)):
            portal.iscsi_target_portal_tag = idx
            portal.save()
        started = notifier().reload("iscsitarget")
        if started is False and services.objects.get(
                srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget",
                                _("The iSCSI service failed to reload."))


class iSCSITargetPortalIP(Model):
    iscsi_target_portalip_portal = models.ForeignKey(
        iSCSITargetPortal,
        verbose_name=_("Portal"),
        related_name='ips',
    )
    iscsi_target_portalip_ip = models.IPAddressField(
        verbose_name=_("IP Address"),
    )
    iscsi_target_portalip_port = models.SmallIntegerField(
        verbose_name=_("Port"),
        default=3260,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
    )

    class Meta:
        unique_together = (
            ('iscsi_target_portalip_ip', 'iscsi_target_portalip_port'),
            )
        verbose_name = _("Portal IP")

    def __unicode__(self):
        return "%s:%d" % (
            self.iscsi_target_portalip_ip,
            self.iscsi_target_portalip_port,
        )


class iSCSITargetAuthorizedInitiator(Model):
    iscsi_target_initiator_tag = models.IntegerField(
        default=1,
        unique=True,
        verbose_name=_("Group ID"),
    )
    iscsi_target_initiator_initiators = models.TextField(
        max_length=2048,
        verbose_name=_("Initiators"),
        default="ALL",
        help_text=_("Initiator authorized to access to the iSCSI target. "
                    "It takes a name or 'ALL' for any initiators."),
    )
    iscsi_target_initiator_auth_network = models.TextField(
        max_length=2048,
        verbose_name=_("Authorized network"),
        default="ALL",
        help_text=_("Network authorized to access to the iSCSI target. "
                    "It takes IP or CIDR addresses or 'ALL' for any IPs."),
    )
    iscsi_target_initiator_comment = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Comment"),
        help_text=_("You may enter a description here for your reference."),
    )

    class Meta:
        verbose_name = _("Initiator")
        verbose_name_plural = _("Initiators")

    class FreeAdmin:
        menu_child_of = "sharing.ISCSI"
        icon_object = u"InitiatorIcon"
        icon_model = u"InitiatorIcon"
        icon_add = u"AddInitiatorIcon"
        icon_view = u"ViewAllInitiatorsIcon"
        nav_extra = {'order': 0}
        resource_name = 'services/iscsi/authorizedinitiator'

    def __unicode__(self):
        if self.iscsi_target_initiator_comment != "":
            return u"%s (%s)" % (
                self.iscsi_target_initiator_tag,
                self.iscsi_target_initiator_comment,
                )
        else:
            return unicode(self.iscsi_target_initiator_tag)

    def delete(self):
        super(iSCSITargetAuthorizedInitiator, self).delete()
        portals = iSCSITargetAuthorizedInitiator.objects.all().order_by(
            'iscsi_target_initiator_tag')
        idx = 1
        for portal in portals:
            portal.iscsi_target_initiator_tag = idx
            portal.save()
            idx += 1


class iSCSITargetAuthCredential(Model):
    iscsi_target_auth_tag = models.IntegerField(
        default=1,
        verbose_name=_("Group ID"),
    )
    iscsi_target_auth_user = models.CharField(
        max_length=120,
        verbose_name=_("User"),
        help_text=_("Target side user name. It is usually the initiator "
                    "name by default."),
    )
    iscsi_target_auth_secret = models.CharField(
        max_length=120,
        verbose_name=_("Secret"),
        help_text=_("Target side secret."),
    )
    iscsi_target_auth_peeruser = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Peer User"),
        help_text=_("Initiator side user name."),
    )
    iscsi_target_auth_peersecret = models.CharField(
        max_length=120,
        verbose_name=_("Peer Secret"),
        blank=True,
        help_text=_("Initiator side secret. (for mutual CHAP authentication)"),
    )

    class Meta:
        verbose_name = _("Authorized Access")
        verbose_name_plural = _("Authorized Accesses")

    def __init__(self, *args, **kwargs):
        super(iSCSITargetAuthCredential, self).__init__(*args, **kwargs)
        if self.iscsi_target_auth_secret:
            self.iscsi_target_auth_secret = notifier().pwenc_decrypt(
                self.iscsi_target_auth_secret
            )
        self._iscsi_target_auth_secret_encrypted = False

        if self.iscsi_target_auth_peersecret:
            self.iscsi_target_auth_peersecret = notifier().pwenc_decrypt(
                self.iscsi_target_auth_peersecret
            )
        self._iscsi_target_auth_peersecret_encrypted = False

    def save(self, *args, **kwargs):
        if (
            self.iscsi_target_auth_secret and
            not self._iscsi_target_auth_secret_encrypted
        ):
            self.iscsi_target_auth_secret = notifier().pwenc_encrypt(
                self.iscsi_target_auth_secret
            )
            self._iscsi_target_auth_secret_encrypted = True
        if (
            self.iscsi_target_auth_peersecret and
            not self._iscsi_target_auth_peersecret_encrypted
        ):
            self.iscsi_target_auth_peersecret = notifier().pwenc_encrypt(
                self.iscsi_target_auth_peersecret
            )
        super(iSCSITargetAuthCredential, self).save(*args, **kwargs)

    def __unicode__(self):
        return unicode(self.iscsi_target_auth_tag)


class iSCSITarget(Model):
    iscsi_target_name = models.CharField(
        unique=True,
        max_length=120,
        verbose_name=_("Target Name"),
        help_text=_("Base Name will be appended automatically when "
                    "starting without 'iqn.', 'eui.' or 'naa.'."),
    )
    iscsi_target_alias = models.CharField(
        unique=True,
        blank=True,
        null=True,
        max_length=120,
        verbose_name=_("Target Alias"),
        help_text=_("Optional user-friendly string of the target."),
    )
    iscsi_target_mode = models.CharField(
        choices=(
            ('iscsi', _('iSCSI')),
            ('fc', _('Fiber Channel')),
            ('both', _('Both')),
        ),
        default='iscsi',
        max_length=20,
        verbose_name=_('Target Mode'),
    )

    class Meta:
        verbose_name = _("Target")
        verbose_name_plural = _("Targets")
        ordering = ['iscsi_target_name']

    def __unicode__(self):
        return self.iscsi_target_name

    def delete(self):
        for te in iSCSITargetToExtent.objects.filter(iscsi_target=self):
            te.delete()
        super(iSCSITarget, self).delete()
        started = notifier().reload("iscsitarget")
        if started is False and services.objects.get(
                srv_service='iscsitarget').srv_enable:
            raise ServiceFailed(
                "iscsitarget",
                _("The iSCSI service failed to reload.")
            )


class iSCSITargetGroups(Model):
    iscsi_target = models.ForeignKey(
        iSCSITarget,
        verbose_name=_("Target"),
        help_text=_("Target this group belongs to"),
    )
    iscsi_target_portalgroup = models.ForeignKey(
        iSCSITargetPortal,
        verbose_name=_("Portal Group ID"),
    )
    iscsi_target_initiatorgroup = models.ForeignKey(
        iSCSITargetAuthorizedInitiator,
        verbose_name=_("Initiator Group ID"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    iscsi_target_authtype = models.CharField(
        max_length=120,
        choices=choices.AUTHMETHOD_CHOICES,
        default="None",
        verbose_name=_("Auth Method"),
        help_text=_("The authentication method accepted by the target."),
    )
    iscsi_target_authgroup = models.IntegerField(
        max_length=120,
        verbose_name=_("Authentication Group ID"),
        null=True,
        blank=True,
    )
    iscsi_target_initialdigest = models.CharField(
        max_length=120,
        default="Auto",
        verbose_name=_("Auth Method"),
        help_text=_("The method can be accepted by the target. Auto means "
                    "both none and authentication."),
    )

    def __unicode__(self):
        return 'iSCSI Target Group (%s,%d)' % (
            self.iscsi_target,
            self.id,
        )

    class Meta:
        verbose_name = _("iSCSI Groups")
        verbose_name_plural = _("iSCSI Groups")
        unique_together = (
            ('iscsi_target', 'iscsi_target_portalgroup'),
        )


class iSCSITargetToExtent(Model):
    iscsi_target = models.ForeignKey(
        iSCSITarget,
        verbose_name=_("Target"),
        help_text=_("Target this extent belongs to"),
    )
    iscsi_lunid = models.IntegerField(
        verbose_name=_('LUN ID'),
        null=True,
    )
    iscsi_extent = models.ForeignKey(
        iSCSITargetExtent,
        verbose_name=_("Extent"),
    )

    class Meta:
        ordering = ['iscsi_target', 'iscsi_lunid']
        verbose_name = _("Target / Extent")
        verbose_name_plural = _("Targets / Extents")
        unique_together = (
            'iscsi_target',
            'iscsi_extent',
        )

    def __unicode__(self):
        return unicode(self.iscsi_target) + u' / ' + unicode(self.iscsi_extent)

    def delete(self):
        super(iSCSITargetToExtent, self).delete()
        started = notifier().reload("iscsitarget")
        if started is False and services.objects.get(
                srv_service='iscsitarget').srv_enable:
            raise ServiceFailed("iscsitarget",
                                _("The iSCSI service failed to reload."))


class FiberChannelToTarget(Model):
    fc_port = models.CharField(
        verbose_name=_('Port'),
        max_length=10,
    )
    fc_target = models.ForeignKey(
        iSCSITarget,
        verbose_name=_("Target"),
        help_text=_("Target this extent belongs to"),
        null=True,
    )

    class Meta:
        verbose_name = _('Fiber Channel Target')
        verbose_name_plural = _('Fiber Channel Targets')


class DynamicDNS(NewModel):
    ddns_provider = models.CharField(
        max_length=120,
        choices=choices.DYNDNSPROVIDER_CHOICES,
        default=choices.DYNDNSPROVIDER_CHOICES[0][0],
        blank=True,
        verbose_name=_("Provider"),
    )
    ddns_ipserver = models.CharField(
        max_length=150,
        verbose_name=_('IP Server'),
        # todo: fix default not showing up in the form
        default='checkip.dyndns.org:80 /.',
        help_text=_(
            'The client IP is detected by calling \'url\' from this '
            '\'ip_server_name:port /.\'. Leaving this field blank causes '
            'the service to use its built in default: '
            'checkip.dyndns.org:80 /.'),
        blank=True,
    )
    ddns_domain = models.CharField(
        max_length=120,
        verbose_name=_("Domain name"),
        blank=True,
        help_text=_("A host name alias. This option can appear multiple "
                    "times, for each domain that has the same IP. Use a comma "
                    "to separate multiple alias names.  Some Dynamic DNS "
                    "providers " "require a hash after the host name, for "
                    "these providers use a # sign in the between the hostname "
                    "and hash in the format hostname#hash.  You may also use "
                    "multiple hostname and hash " "combinations in the format "
                    "host1#hash1,host2#hash2."),
    )
    ddns_username = models.CharField(
        max_length=120,
        verbose_name=_("Username"),
    )
    ddns_password = models.CharField(
        max_length=120,
        verbose_name=_("Password"),
    )
    ddns_updateperiod = models.IntegerField(
        verbose_name=_("Update period"),
        blank=True,
        help_text=_("Time in seconds. Default is about 1 min."),
    )
    ddns_fupdateperiod = models.IntegerField(
        verbose_name=_("Forced update period"),
        blank=True,
    )
    ddns_options = models.TextField(
        verbose_name=_("Auxiliary parameters"),
        blank=True,
        help_text=_(
            "These parameters will be added to global settings in "
            "inadyn-mt.conf."),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("Dynamic DNS")
        verbose_name_plural = _("Dynamic DNS")

    class FreeAdmin:
        deletable = False
        icon_model = u"DDNSIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('ddns_provider', 'provider'),
            ('ddns_ipserver', 'ipserver'),
            ('ddns_domain', 'domain'),
            ('ddns_username', 'username'),
            ('ddns_password', 'password'),
            ('ddns_updateperiod', 'update_period'),
            ('ddns_fupdateperiod', 'force_update_period'),
            ('ddns_options', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.dyndns.get_config')
        return cls(**dict(
            id=1,
            ddns_provider=config['provider'],
            ddns_ipserver=config['ipserver'],
            ddns_domain=','.join(config['domains'] or []),
            ddns_username=config['username'],
            ddns_password=config['password'],
            ddns_updateperiod=config['update_period'],
            ddns_fupdateperiod=config['force_update_period'],
            ddns_options=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'provider': self.ddns_provider or None,
            'ipserver': self.ddns_ipserver or None,
            'domains': self.ddns_domain.split(','),
            'username': self.ddns_username,
            'password': self.ddns_password,
            'update_period': self.ddns_updateperiod or None,
            'force_update_period': self.ddns_fupdateperiod or None,
            'auxiliary': self.ddns_options or None,
        }
        self._save_task_call('service.dyndns.configure', data)
        return True


class SNMP(NewModel):
    snmp_location = models.CharField(
        max_length=255,
        verbose_name=_("Location"),
        blank=True,
        help_text=_("Location information, e.g. physical location of this "
                    "system: 'Floor of building, Room xyzzy'."),
    )
    snmp_contact = models.CharField(
        max_length=120,
        verbose_name=_("Contact"),
        blank=True,
        help_text=_("Contact information, e.g. name or email of the "
                    "person responsible for this system: "
                    "'admin@email.address'."),
    )
    snmp_v3 = models.BooleanField(
        verbose_name=_('SNMP v3 Support'),
        default=False,
    )
    snmp_community = models.CharField(
        max_length=120,
        default='public',
        verbose_name=_("Community"),
        help_text=_("In most cases, 'public' is used here."),
        blank=True,
    )
    snmp_v3_username = models.CharField(
        blank=True,
        max_length=20,
        verbose_name=_('Username'),
    )
    snmp_v3_authtype = models.CharField(
        blank=True,
        choices=(
            ('MD5', _('MD5')),
            ('SHA', _('SHA')),
        ),
        default='SHA',
        max_length=3,
        verbose_name=_('Authentication Type'),
    )
    snmp_v3_password = models.CharField(
        blank=True,
        max_length=50,
        verbose_name=_('Password'),
    )
    snmp_v3_privproto = models.CharField(
        blank=True,
        choices=(
            ('AES', _('AES')),
            ('DES', _('DES')),
        ),
        max_length=3,
        null=True,
        verbose_name=_('Privacy Protocol'),
    )
    snmp_v3_privpassphrase = models.CharField(
        blank=True,
        max_length=100,
        null=True,
        verbose_name=_('Privacy Passphrase'),
    )
    snmp_options = models.TextField(
        verbose_name=_("Auxiliary parameters"),
        blank=True,
        help_text=_("These parameters will be added to /etc/snmpd.config."),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("SNMP")
        verbose_name_plural = _("SNMP")

    class FreeAdmin:
        deletable = False
        icon_model = u"SNMPIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('snmp_location', 'location'),
            ('snmp_contact', 'contact'),
            ('snmp_v3', 'v3'),
            ('snmp_community', 'community'),
            ('snmp_v3_username', 'v3_username'),
            ('snmp_v3_authtype', 'v3_auth_type'),
            ('snmp_v3_password', 'v3_password'),
            ('snmp_v3_privproto', 'v3_privacy_protocol'),
            ('snmp_v3_privpassphrase', 'v3_privacy_passphrase'),
            ('snmp_options', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.snmp.get_config')
        return cls(**dict(
            id=1,
            snmp_location=config['location'],
            snmp_contact=config['contact'],
            snmp_v3=config['v3'],
            snmp_community=config['community'],
            snmp_v3_username=config['v3_username'],
            snmp_v3_authtype=config['v3_auth_type'],
            snmp_v3_password=config['v3_password'],
            snmp_v3_privproto=config['v3_privacy_protocol'],
            snmp_v3_privpassphrase=config['v3_privacy_passphrase'],
            snmp_options=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'location': self.snmp_location or None,
            'contact': self.snmp_contact or None,
            'v3': self.snmp_v3,
            'community': self.snmp_community or None,
            'v3_auth_type': self.snmp_v3_authtype or 'SHA',
            'v3_privacy_protocol': self.snmp_v3_privproto or 'AES',
            'v3_privacy_passphrase': self.snmp_v3_privpassphrase or None,
            'auxiliary': self.snmp_options or None,
        }
        if self.snmp_v3_username:
            data['v3_username'] = self.snmp_v3_username
        if self.snmp_v3_password:
            data['v3_password'] = self.snmp_v3_password
        self._save_task_call('service.snmp.configure', data)
        return True


class UPS(NewModel):
    ups_mode = models.CharField(
        default='master',
        max_length=6,
        choices=(
            ('MASTER', _("Master")),
            ('SLAVE', _("Slave")),
        ),
        verbose_name=_("UPS Mode"),
    )
    ups_identifier = models.CharField(
        max_length=120,
        verbose_name=_("Identifier"),
        default='ups',
        help_text=_(
            "This name is used to uniquely identify your UPS on this system."),
    )
    ups_remotehost = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Remote Host"),
    )
    ups_remoteport = models.IntegerField(
        default=3493,
        blank=True,
        verbose_name=_("Remote Port"),
    )
    ups_driver = models.CharField(
        max_length=120,
        verbose_name=_("Driver"),
        choices=choices.UPSDRIVER_CHOICES(),
        blank=True,
        help_text=_("The driver used to communicate with your UPS."),
    )
    ups_port = models.CharField(
        max_length=120,
        verbose_name=_("Port"),
        blank=True,
        help_text=_("The serial or USB port where your UPS is connected."),
    )
    ups_options = models.TextField(
        verbose_name=_("Auxiliary parameters (ups.conf)"),
        blank=True,
        help_text=_("Additional parameters to the hardware-specific part "
                    "of the driver."),
    )
    ups_description = models.CharField(
        max_length=120,
        verbose_name=_("Description"),
        blank=True,
    )
    ups_shutdown = models.CharField(
        max_length=120,
        choices=choices.UPS_CHOICES,
        default='batt',
        verbose_name=_("Shutdown mode"),
    )
    ups_shutdowntimer = models.IntegerField(
        verbose_name=_("Shutdown timer"),
        default=30,
        help_text=_(
            "The time in seconds until shutdown is initiated. If the UPS "
            "happens to come back before the time is up the "
            "shutdown is canceled."),
    )
    ups_monuser = models.CharField(
        max_length=50,
        default='upsmon',
        verbose_name=_("Monitor User")
    )
    ups_monpwd = models.CharField(
        max_length=30,
        default="fixmepass",
        verbose_name=_("Monitor Password"),
    )
    ups_extrausers = models.TextField(
        blank=True,
        verbose_name=_("Extra users (upsd.users)"),
    )
    ups_rmonitor = models.BooleanField(
        verbose_name=_("Remote Monitor"),
        default=False,
    )
    ups_emailnotify = models.BooleanField(
        verbose_name=_("Send Email Status Updates"),
        default=False,
    )
    ups_toemail = models.CharField(
        max_length=120,
        verbose_name=_("To email"),
        blank=True,
        help_text=_("Destination email address. Separate email addresses "
                    "by semi-colon."),
    )
    ups_subject = models.CharField(
        max_length=120,
        verbose_name=_("Email Subject"),
        default='UPS report generated by %h',
        help_text=_(
            "The subject of the email. You can use the following "
            "parameters for substitution:<br /><ul><li>%d - Date</li><li>"
            "%h - Hostname</li></ul>"),
    )
    ups_powerdown = models.BooleanField(
        verbose_name=_("Power Off UPS"),
        help_text=_("Signal the UPS to power off after FreeNAS shuts down."),
        default=True,
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("UPS")
        verbose_name_plural = _("UPS")

    class FreeAdmin:
        deletable = False
        icon_model = u"UPSIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('ups_mode', 'mode'),
            ('ups_identifier', 'identifier'),
            ('ups_remotehost', 'remote_host'),
            ('ups_remoteport', 'remote_port'),
            ('ups_driver', 'driver'),
            ('ups_port', 'driver_port'),
            ('ups_options', 'auxiliary'),
            ('ups_description', 'description'),
            ('ups_shutdown', 'shutdown_mode'),
            ('ups_shutdowntimer', 'shutdown_timer'),
            ('ups_monuser', 'monitor_user'),
            ('ups_monpwd', 'monitor_password'),
            ('ups_extrausers', 'auxiliary_users'),
            ('ups_rmonitor', 'monitor_remote'),
            ('ups_emailnotify', 'email_notify'),
            ('ups_toemail', 'email_recipients'),
            ('ups_subject', 'email_subject'),
            ('ups_powerdown', 'powerdown'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.ups.get_config')
        return cls(**dict(
            id=1,
            ups_mode=config['mode'],
            ups_identifier=config['identifier'],
            ups_remotehost=config['remote_host'],
            ups_remoteport=config['remote_port'],
            ups_driver=config['driver'],
            ups_port=config['driver_port'],
            ups_options=config['auxiliary'],
            ups_description=config['description'],
            ups_shutdown=config['shutdown_mode'],
            ups_shutdowntimer=config['shutdown_timer'],
            ups_monuser=config['monitor_user'],
            ups_monpwd=config['monitor_password'],
            ups_extrausers=config['auxiliary_users'],
            ups_rmonitor=config['monitor_remote'],
            ups_emailnotify=config['email_notify'],
            ups_toemail=';'.join(config['email_recipients']),
            ups_subject=config['email_subject'],
            ups_powerdown=config['powerdown'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'mode': self.ups_mode,
            'identifier': self.ups_identifier,
            'remote_host': self.ups_remotehost or None,
            'remote_port': self.ups_remoteport,
            'driver': self.ups_driver,
            'driver_port': self.ups_port,
            'auxiliary': self.ups_options or None,
            'description': self.ups_description or None,
            'shutdown_mode': self.ups_shutdown,
            'shutdown_timer': self.ups_shutdowntimer,
            'monitor_user': self.ups_monuser,
            'monitor_password': self.ups_monpwd,
            'auxiliary_users': self.ups_extrausers or None,
            'monitor_remote': self.ups_rmonitor,
            'email_notify': self.ups_emailnotify,
            'email_recipients': [i.strip() for i in self.ups_toemail.split(';') if self.ups_toemail],
            'email_subject': self.ups_subject,
            'powerdown': self.ups_powerdown,
        }
        self._save_task_call('service.ups.configure', data)
        return True


class FTP(NewModel):
    ftp_port = models.PositiveIntegerField(
        default=21,
        verbose_name=_("Port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text=_("Port to bind FTP server."),
    )
    ftp_clients = models.PositiveIntegerField(
        default=32,
        verbose_name=_("Clients"),
        validators=[MinValueValidator(0), MaxValueValidator(10000)],
        help_text=_("Maximum number of simultaneous clients."),
    )
    ftp_ipconnections = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Connections"),
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        help_text=_("Maximum number of connections per IP address "
                    "(0 = unlimited)."),
    )
    ftp_loginattempt = models.PositiveIntegerField(
        default=3,
        verbose_name=_("Login Attempts"),
        validators=[MinValueValidator(0), MaxValueValidator(1000)],
        help_text=_("Maximum number of allowed password attempts before "
                    "disconnection."),
    )
    ftp_timeout = models.PositiveIntegerField(
        default=120,
        verbose_name=_("Timeout"),
        validators=[MinValueValidator(0), MaxValueValidator(10000)],
        help_text=_("Maximum idle time in seconds."),
    )
    ftp_rootlogin = models.BooleanField(
        verbose_name=_("Allow Root Login"),
        default=False,
    )
    ftp_onlyanonymous = models.BooleanField(
        verbose_name=_("Allow Anonymous Login"),
        default=False,
    )
    ftp_anonpath = PathField(
        blank=True,
        verbose_name=_("Path"))
    ftp_onlylocal = models.BooleanField(
        verbose_name=_("Allow Local User Login"),
        default=False,
    )
    # FIXME: rename the field
    ftp_banner = models.TextField(
        max_length=120,
        verbose_name=_("Display Login"),
        blank=True,
        help_text=_(
            "Message which will be displayed to the user when they initially "
            "login."),
    )
    ftp_filemask = models.CharField(
        max_length=3,
        default="077",
        verbose_name=_("File mask"),
        help_text=_("Use this option to override the file creation mask "
                    "(077 by default)."),
    )
    ftp_dirmask = models.CharField(
        max_length=3,
        default="077",
        verbose_name=_("Directory mask"),
        help_text=_(
            "Use this option to override the directory creation mask "
            "(077 by default)."),
    )
    ftp_fxp = models.BooleanField(
        verbose_name=_("Enable FXP"),
        default=False,
    )
    ftp_resume = models.BooleanField(
        verbose_name=_("Allow Transfer Resumption"),
        default=False,
    )
    ftp_defaultroot = models.BooleanField(
        verbose_name=_("Always Chroot"),
        help_text=_(
            "For local users, only allow access to user home directory unless "
            "the user is a member of group wheel."),
        default=False,
    )
    ftp_ident = models.BooleanField(
        verbose_name=_("Require IDENT Authentication"),
        default=False,
    )
    ftp_reversedns = models.BooleanField(
        verbose_name=_("Perform Reverse DNS Lookups"),
        default=False,
    )
    ftp_masqaddress = models.CharField(
        verbose_name=_("Masquerade address"),
        blank=True,
        max_length=120,
        help_text=_("Causes the server to display the network information "
                    "for the specified address to the client, on the "
                    "assumption that IP address or DNS host is acting as a "
                    "NAT gateway or port forwarder for the server."),
    )
    ftp_passiveportsmin = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Minimum passive port"),
        help_text=_("The minimum port to allocate for PASV style data "
                    "connections (0 = use any port)."),
    )
    ftp_passiveportsmax = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Maximum passive port"),
        help_text=_("The maximum port to allocate for PASV style data "
                    "connections (0 = use any port). Passive ports restricts "
                    "the range of ports from which the server will select "
                    "when sent the PASV command from a client. The server "
                    "will randomly " "choose a number from within the "
                    "specified range until an open" " port is found. The port "
                    "range selected must be in the " "non-privileged range "
                    "(eg. greater than or equal to 1024). It is strongly "
                    "recommended that the chosen range be large enough to "
                    "handle many simultaneous passive connections (for "
                    "example, 49152-65534, the IANA-registered ephemeral port "
                    "range)."),
    )
    ftp_localuserbw = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Local user upload bandwidth"),
        help_text=_("Local user upload bandwidth in KB/s. Zero means "
                    "infinity."),
    )
    ftp_localuserdlbw = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Local user download bandwidth"),
        help_text=_("Local user download bandwidth in KB/s. Zero means "
                    "infinity."),
    )
    ftp_anonuserbw = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Anonymous user upload bandwidth"),
        help_text=_("Anonymous user upload bandwidth in KB/s. Zero means "
                    "infinity."),
    )
    ftp_anonuserdlbw = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Anonymous user download bandwidth"),
        help_text=_("Anonymous user download bandwidth in KB/s. Zero means "
                    "infinity."),
    )
    ftp_tls = models.BooleanField(
        verbose_name=_("Enable TLS"),
        default=False,
    )
    ftp_tls_policy = models.CharField(
        max_length=120,
        choices=choices.FTP_TLS_POLICY_CHOICES,
        default="on",
        verbose_name=_("TLS policy"),
    )
    ftp_tls_opt_allow_client_renegotiations = models.BooleanField(
        verbose_name=_("TLS allow client renegotiations"),
        default=False,
    )
    ftp_tls_opt_allow_dot_login = models.BooleanField(
        verbose_name=_("TLS allow dot login"),
        default=False,
    )
    ftp_tls_opt_allow_per_user = models.BooleanField(
        verbose_name=_("TLS allow per user"),
        default=False,
    )
    ftp_tls_opt_common_name_required = models.BooleanField(
        verbose_name=_("TLS common name required"),
        default=False,
    )
    ftp_tls_opt_enable_diags = models.BooleanField(
        verbose_name=_("TLS enable diagnostics"),
        default=False,
    )
    ftp_tls_opt_export_cert_data = models.BooleanField(
        verbose_name=_("TLS export certificate data"),
        default=False,
    )
    ftp_tls_opt_no_cert_request = models.BooleanField(
        verbose_name=_("TLS no certificate request"),
        default=False,
    )
    ftp_tls_opt_no_empty_fragments = models.BooleanField(
        verbose_name=_("TLS no empty fragments"),
        default=False,
    )
    ftp_tls_opt_no_session_reuse_required = models.BooleanField(
        verbose_name=_("TLS no session reuse required"),
        default=False,
    )
    ftp_tls_opt_stdenvvars = models.BooleanField(
        verbose_name=_("TLS export standard vars"),
        default=False,
    )
    ftp_tls_opt_dns_name_required = models.BooleanField(
        verbose_name=_("TLS DNS name required"),
        default=False,
    )
    ftp_tls_opt_ip_address_required = models.BooleanField(
        verbose_name=_("TLS IP address required"),
        default=False,
    )
    ftp_ssltls_certificate = models.ForeignKey(
        Certificate,
        verbose_name=_("Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    ftp_options = models.TextField(
        max_length=120,
        verbose_name=_("Auxiliary parameters"),
        blank=True,
        help_text=_("These parameters are added to proftpd.conf."),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("FTP")
        verbose_name_plural = _("FTP")

    class Middleware:
        configstore = True
        field_mapping = (
            ('ftp_port', 'port'),
            ('ftp_clients', 'max_clients'),
            ('ftp_ipconnections', 'ip_connections'),
            ('ftp_loginattempt', 'login_attempt'),
            ('ftp_timeout', 'timeout'),
            ('ftp_rootlogin', 'root_login'),
            ('ftp_onlyanonymous', 'only_anonymous'),
            ('ftp_anonpath', 'anonymous_path'),
            ('ftp_onlylocal', 'only_local'),
            ('ftp_banner', 'display_login'),
            ('ftp_filemask', 'filemask'),
            ('ftp_dirmask', 'dirmask'),
            ('ftp_fxp', 'fxp'),
            ('ftp_resume', 'resume'),
            ('ftp_defaultroot', 'chroot'),
            ('ftp_ident', 'ident'),
            ('ftp_reversedns', 'reverse_dns'),
            ('ftp_masqaddress', 'masquerade_address'),
            ('ftp_passiveportsmin', 'passive_ports_min'),
            ('ftp_passiveportsmax', 'passive_ports_max'),
            ('ftp_localuserbw', 'local_up_bandwidth'),
            ('ftp_localuserdlbw', 'local_down_bandwidth'),
            ('ftp_anonuserbw', 'anon_up_bandwidth'),
            ('ftp_anonuserdlbw', 'anon_down_bandwidth'),
            ('ftp_tls', 'tls'),
            ('ftp_tls_policy', 'tls_policy'),
            ('ftp_ssltls_certificate', 'tls_ssl_certificate'),
            ('ftp_options', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.ftp.get_config')
        if config['tls_ssl_certificate']:
            certificate = Certificate.objects.get(id=config['tls_ssl_certificate'])
        else:
            certificate = None

        ftp_tls_opt_allow_client_renegotiations = False
        ftp_tls_opt_allow_dot_login = False
        ftp_tls_opt_allow_per_user = False
        ftp_tls_opt_common_name_required = False
        ftp_tls_opt_enable_diags = False
        ftp_tls_opt_export_cert_data = False
        ftp_tls_opt_no_cert_request = False
        ftp_tls_opt_no_empty_fragments = False
        ftp_tls_opt_no_session_reuse_required = False
        ftp_tls_opt_stdenvvars = False
        ftp_tls_opt_dns_name_required = False
        ftp_tls_opt_ip_address_required = False
        if config['tls_options']:
            if 'ALLOW_CLIENT_RENEGOTIATIONS' in config['tls_options']:
                ftp_tls_opt_allow_client_renegotiations = True
            elif 'ALLOW_DOT_LOGIN' in config['tls_options']:
                ftp_tls_opt_allow_dot_login = True
            elif 'ALLOW_PER_USER' in config['tls_options']:
                ftp_tls_opt_allow_per_user = True
            elif 'COMMON_NAME_REQUIRED' in config['tls_options']:
                ftp_tls_opt_common_name_required = True
            elif 'ENABLE_DIAGNOSTICS' in config['tls_options']:
                ftp_tls_opt_enable_diags = True
            elif 'EXPORT_CERTIFICATE_DATA' in config['tls_options']:
                ftp_tls_opt_export_cert_data = True
            elif 'NO_CERTIFICATE_REQUEST' in config['tls_options']:
                ftp_tls_opt_no_cert_request = True
            elif 'NO_EMPTY_FRAGMENTS' in config['tls_options']:
                ftp_tls_opt_no_empty_fragments = True
            elif 'NO_SESSION_REUSE_REQUIRED' in config['tls_options']:
                ftp_tls_opt_no_session_reuse_required = True
            elif 'STANDARD_ENV_VARS' in config['tls_options']:
                ftp_tls_opt_stdenvvars = True
            elif 'DNS_NAME_REQUIRED' in config['tls_options']:
                ftp_tls_opt_dns_name_required = True
            elif 'IP_ADDRESS_REQUIRED' in config['tls_options']:
                ftp_tls_opt_ip_address_required = True

        return cls(**dict(
            id=1,
            ftp_port=config['port'],
            ftp_clients=config['max_clients'],
            ftp_ipconnections=config['ip_connections'],
            ftp_loginattempt=config['login_attempt'],
            ftp_timeout=config['timeout'],
            ftp_rootlogin=config['root_login'],
            ftp_onlyanonymous=config['only_anonymous'],
            ftp_anonpath=config['anonymous_path'],
            ftp_onlylocal=config['only_local'],
            ftp_banner=config['display_login'],
            ftp_filemask=config['filemask'],
            ftp_dirmask=config['dirmask'],
            ftp_fxp=config['fxp'],
            ftp_resume=config['resume'],
            ftp_defaultroot=config['chroot'],
            ftp_ident=config['ident'],
            ftp_reversedns=config['reverse_dns'],
            ftp_masqaddress=config['masquerade_address'],
            ftp_passiveportsmin=config['passive_ports_min'],
            ftp_passiveportsmax=config['passive_ports_max'],
            ftp_localuserbw=config['local_up_bandwidth'],
            ftp_localuserdlbw=config['local_down_bandwidth'],
            ftp_anonuserbw=config['anon_up_bandwidth'],
            ftp_anonuserdlbw=config['anon_down_bandwidth'],
            ftp_tls=config['tls'],
            ftp_tls_policy=config['tls_policy'].lower(),
            ftp_tls_opt_allow_client_renegotiations=ftp_tls_opt_allow_client_renegotiations,
            ftp_tls_opt_allow_dot_login=ftp_tls_opt_allow_dot_login,
            ftp_tls_opt_allow_per_user=ftp_tls_opt_allow_per_user,
            ftp_tls_opt_common_name_required=ftp_tls_opt_common_name_required,
            ftp_tls_opt_enable_diags=ftp_tls_opt_enable_diags,
            ftp_tls_opt_export_cert_data=ftp_tls_opt_export_cert_data,
            ftp_tls_opt_no_cert_request=ftp_tls_opt_no_cert_request,
            ftp_tls_opt_no_empty_fragments=ftp_tls_opt_no_empty_fragments,
            ftp_tls_opt_no_session_reuse_required=ftp_tls_opt_no_session_reuse_required,
            ftp_tls_opt_stdenvvars=ftp_tls_opt_stdenvvars,
            ftp_tls_opt_dns_name_required=ftp_tls_opt_dns_name_required,
            ftp_tls_opt_ip_address_required=ftp_tls_opt_ip_address_required,
            ftp_ssltls_certificate=certificate,
            ftp_options=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        tls_options = []
        if self.ftp_tls_opt_allow_client_renegotiations:
            tls_options.append('ALLOW_CLIENT_RENEGOTIATIONS')
        if self. ftp_tls_opt_allow_dot_login:
            tls_options.append('ALLOW_DOT_LOGIN')
        if self.ftp_tls_opt_allow_per_user:
            tls_options.append('ALLOW_PER_USER')
        if self.ftp_tls_opt_common_name_required:
            tls_options.append('COMMON_NAME_REQUIRED')
        if self.ftp_tls_opt_enable_diags:
            tls_options.append('ENABLE_DIAGNOSTICS')
        if self.ftp_tls_opt_export_cert_data:
            tls_options.append('EXPORT_CERTIFICATE_DATA')
        if self.ftp_tls_opt_no_cert_request:
            tls_options.append('NO_CERTIFICATE_REQUEST')
        if self.ftp_tls_opt_no_empty_fragments:
            tls_options.append('NO_EMPTY_FRAGMENTS')
        if self.ftp_tls_opt_no_session_reuse_required:
            tls_options.append('NO_SESSION_REUSE_REQUIRED')
        if self.ftp_tls_opt_stdenvvars:
            tls_options.append('STANDARD_ENV_VARS')
        if self.ftp_tls_opt_dns_name_required:
            tls_options.append('DNS_NAME_REQUIRED')
        if self.ftp_tls_opt_ip_address_required:
            tls_options.append('IP_ADDRESS_REQUIRED')
        data = {
            'port': self.ftp_port,
            'max_clients': self.ftp_clients,
            'ip_connections': self.ftp_ipconnections,
            'login_attempt': self.ftp_loginattempt,
            'timeout': self.ftp_timeout,
            'root_login': self.ftp_rootlogin,
            'only_anonymous': self.ftp_onlyanonymous,
            'anonymous_path': self.ftp_anonpath,
            'only_local': self.ftp_onlylocal,
            'display_login': self.ftp_banner,
            'filemask': self.ftp_filemask,
            'dirmask': self.ftp_dirmask,
            'fxp': self.ftp_fxp,
            'resume': self.ftp_resume,
            'chroot': self.ftp_defaultroot,
            'ident': self.ftp_ident,
            'reverse_dns': self.ftp_reversedns,
            'masquerade_address': self.ftp_masqaddress,
            'passive_ports_min': self.ftp_passiveportsmin,
            'passive_ports_max': self.ftp_passiveportsmax,
            'local_up_bandwidth': self.ftp_localuserbw,
            'local_down_bandwidth': self.ftp_localuserdlbw,
            'anon_up_bandwidth': self.ftp_anonuserbw,
            'anon_down_bandwidth': self.ftp_anonuserdlbw,
            'tls': self.ftp_tls,
            'tls_policy': self.ftp_tls_policy.upper(),
            'tls_options': tls_options,
            'tls_ssl_certificate': self.ftp_ssltls_certificate.id if self.ftp_ssltls_certificate else None,
            'auxiliary': self.ftp_options or None,
        }
        self._save_task_call('service.ftp.configure', data)
        return True


class TFTP(NewModel):
    tftp_directory = PathField(
        verbose_name=_("Directory"),
        help_text=_("The directory containing the files you want to "
                    "publish. The remote host does not need to pass along the "
                    "directory as part of the transfer."),
    )
    tftp_newfiles = models.BooleanField(
        verbose_name=_("Allow New Files"),
        default=False,
    )
    tftp_port = models.PositiveIntegerField(
        verbose_name=_("Port"),
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        default=69,
        help_text=_("The port to listen to. The default is to listen to "
                    "the tftp port specified in /etc/services."),
    )
    tftp_username = UserField(
        max_length=120,
        default="nobody",
        verbose_name=_("Username"),
        help_text=_("Specifies the username which the service will run "
                    "as."),
    )
    tftp_umask = models.CharField(
        max_length=120,
        verbose_name=_("umask"),
        default='022',
        help_text=_("Set the umask for newly created files to the "
                    "specified value. The default is 022 (everyone can read, "
                    "nobody can write)."),
    )
    tftp_options = models.CharField(
        max_length=120,
        verbose_name=_("Extra options"),
        blank=True,
        help_text=_("Extra command line options (usually empty)."),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("TFTP")
        verbose_name_plural = _("TFTP")

    class FreeAdmin:
        deletable = False
        icon_model = "TFTPIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('tftp_directory', 'path'),
            ('tftp_newfiles', 'allow_new_files'),
            ('tftp_port', 'port'),
            ('tftp_username', 'username'),
            ('tftp_umask', 'umask'),
            ('tftp_options', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.tftp.get_config')
        return cls(**dict(
            id=1,
            tftp_directory=config['path'],
            tftp_newfiles=config['allow_new_files'],
            tftp_port=config['port'],
            tftp_username=config['username'],
            tftp_umask=config['umask'],
            tftp_options=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'path': self.tftp_directory,
            'allow_new_files': self.tftp_newfiles,
            'port': self.tftp_port,
            'username': self.tftp_username,
            'umask': self.tftp_umask,
            'auxiliary': self.tftp_options,
        }
        self._save_task_call('service.tftp.configure', data)
        return True


class SSH(NewModel):
    ssh_tcpport = models.PositiveIntegerField(
        verbose_name=_("TCP Port"),
        default=22,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text=_("Alternate TCP port. Default is 22"),
    )
    ssh_rootlogin = models.BooleanField(
        verbose_name=_("Login as Root with password"),
        help_text=_("Disabled: Root can only login via public key "
                    "authentication; Enabled: Root login permitted with "
                    "password"),
        default=False,
    )
    ssh_passwordauth = models.BooleanField(
        verbose_name=_("Allow Password Authentication"),
        default=False,
    )
    ssh_tcpfwd = models.BooleanField(
        verbose_name=_("Allow TCP Port Forwarding"),
        default=False,
    )
    ssh_compression = models.BooleanField(
        verbose_name=_("Compress Connections"),
        default=False,
    )
    ssh_privatekey = models.TextField(
        max_length=1024,
        verbose_name=_("Host Private Key"),
        blank=True,
        help_text=_("Paste a RSA PRIVATE KEY in PEM format here."),
    )
    ssh_sftp_log_level = models.CharField(
        verbose_name=_("SFTP Log Level"),
        choices=choices.SFTP_LOG_LEVEL,
        blank=True,
        max_length=20,
        help_text=_("Specifies which messages will be logged by "
                    "sftp-server. INFO and VERBOSE log transactions that "
                    "sftp-server performs on behalf of the client. DEBUG2 and "
                    "DEBUG3 each specify higher levels of debugging output. "
                    "The default is ERROR."),
    )
    ssh_sftp_log_facility = models.CharField(
        verbose_name=_("SFTP Log Facility"),
        choices=choices.SFTP_LOG_FACILITY,
        blank=True,
        max_length=20,
        help_text=_("Specifies the facility code that is used when "
                    "logging messages from sftp-server."),
    )
    ssh_options = models.TextField(
        max_length=120,
        verbose_name=_("Extra options"),
        blank=True,
        help_text=_("Extra options to /etc/ssh/sshd_config (usually "
                    "empty). Note, incorrect entered options prevent SSH "
                    "service to be started."),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("SSH")
        verbose_name_plural = _("SSH")

    class FreeAdmin:
        deletable = False
        icon_model = "OpenSSHIcon"
        advanced_fields = (
            'ssh_sftp_log_level',
            'ssh_sftp_log_facility',
            'ssh_privatekey',
            'ssh_options',
        )

    class Middleware:
        configstore = True
        field_mapping = (
            ('ssh_tcpport', 'port'),
            ('ssh_rootlogin', 'permit_root_login'),
            ('ssh_passwordauth', 'allow_password_auth'),
            ('ssh_tcpfwd', 'allow_port_forwarding'),
            ('ssh_compression', 'compression'),
            ('ssh_sftp_log_level', 'sftp_log_level'),
            ('ssh_sftp_log_facility', 'sftp_log_facility'),
            ('ssh_options', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.ssh.get_config')
        return cls(**dict(
            id=1,
            ssh_tcpport=config['port'],
            ssh_rootlogin=config['permit_root_login'],
            ssh_passwordauth=config['allow_password_auth'],
            ssh_tcpfwd=config['allow_port_forwarding'],
            ssh_compression=config['compression'],
            ssh_sftp_log_level=config['sftp_log_level'],
            ssh_sftp_log_facility=config['sftp_log_facility'],
            ssh_options=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'port': self.ssh_tcpport,
            'permit_root_login': self.ssh_rootlogin,
            'allow_password_auth': self.ssh_passwordauth,
            'allow_port_forwarding': self.ssh_tcpfwd,
            'compression': self.ssh_compression,
            'sftp_log_level': self.ssh_sftp_log_level,
            'sftp_log_facility': self.ssh_sftp_log_facility,
            'auxiliary': self.ssh_options or None,
        }
        self._save_task_call('service.ssh.configure', data)
        return True


class LLDP(NewModel):
    lldp_intdesc = models.BooleanField(
        verbose_name=_('Interface Description'),
        default=True,
        help_text=_('Save received info in interface description / alias'),
    )
    lldp_country = models.CharField(
        verbose_name=_('Country Code'),
        max_length=2,
        help_text=_(
            'Specify a two-letterISO 3166 country code (required for LLDP'
            'location support)'),
        blank=True,
    )
    lldp_location = models.CharField(
        verbose_name=_('Location'),
        max_length=200,
        help_text=_('Specify the physical location of the host'),
        blank=True,
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("LLDP")
        verbose_name_plural = _("LLDP")

    class FreeAdmin:
        deletable = False
        icon_model = "LLDPIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('lldp_intdesc', 'save_description'),
            ('lldp_country', 'country_code'),
            ('lldp_location', 'location'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.lldp.get_config')
        return cls(**dict(
            id=1,
            lldp_intdesc=config['save_description'],
            lldp_country=config['country_code'],
            lldp_location=config['location'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'save_description': self.lldp_intdesc,
            'country_code': self.lldp_country or None,
            'location': self.lldp_location or None,
        }
        self._save_task_call('service.lldp.configure', data)
        return True


class Rsyncd(NewModel):
    rsyncd_port = models.IntegerField(
        default=873,
        verbose_name=_("TCP Port"),
        help_text=_("Alternate TCP port. Default is 873"),
    )
    rsyncd_auxiliary = models.TextField(
        blank=True,
        verbose_name=_("Auxiliary parameters"),
        help_text=_("These parameters will be added to [global] settings "
                    "in rsyncd.conf"),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("Configure Rsyncd")
        verbose_name_plural = _("Configure Rsyncd")

    class FreeAdmin:
        deletable = False
        menu_child_of = "services.Rsync"
        icon_model = u"rsyncdIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('rsyncd_port', 'port'),
            ('rsyncd_auxiliary', 'auxiliary'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.rsyncd.get_config')
        return cls(**dict(
            id=1,
            rsyncd_port=config['port'],
            rsyncd_auxiliary=config['auxiliary'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'port': self.rsyncd_port,
            'auxiliary': self.rsyncd_auxiliary or None,
        }
        self._save_task_call('service.rsyncd.configure', data)
        return True


class RsyncMod(NewModel):
    id = models.CharField(
        max_length=200,
        verbose_name=_("ID"),
        primary_key=True,
        editable=False,
    )
    rsyncmod_name = models.CharField(
        max_length=120,
        verbose_name=_("Module name"),
    )
    rsyncmod_comment = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_("Comment"),
    )
    rsyncmod_path = PathField(
        verbose_name=_("Path"),
        help_text=_("Path to be shared"),
    )
    rsyncmod_mode = models.CharField(
        max_length=120,
        choices=choices.ACCESS_MODE,
        default="rw",
        verbose_name=_("Access Mode"),
        help_text=_("This controls the access a remote host has to this "
                    "module"),
    )
    rsyncmod_maxconn = models.IntegerField(
        default=0,
        verbose_name=_("Maximum connections"),
        help_text=_("Maximum number of simultaneous connections. Default "
                    "is 0 (unlimited)"),
    )
    rsyncmod_user = UserField(
        max_length=120,
        default="nobody",
        verbose_name=_("User"),
        help_text=_("This option specifies the user name that file "
                    "transfers to and from that module should take place. In "
                    "combination with the 'Group' option this determines "
                    "what file permissions are available. Leave this field "
                    "empty to use default settings"),
    )
    rsyncmod_group = GroupField(
        max_length=120,
        default="nobody",
        verbose_name=_("Group"),
        help_text=_("This option specifies the group name that file "
                    "transfers to and from that module should take place. "
                    "Leave this field empty to use default settings"),
    )
    rsyncmod_hostsallow = models.TextField(
        verbose_name=_("Hosts allow"),
        help_text=_("This option is a comma, space, or tab delimited set "
                    "of hosts which are permitted to access this module. You "
                    "can " "specify the hosts by name or IP number. Leave "
                    "this field empty to use default settings"),
        blank=True,
    )
    rsyncmod_hostsdeny = models.TextField(
        verbose_name=_("Hosts deny"),
        help_text=_("This option is a comma, space, or tab delimited set "
                    "of host which are NOT permitted to access this module. "
                    "Where " "the lists conflict, the allow list takes "
                    "precedence. In the event that it is necessary to deny "
                    "all by default, use the " "keyword ALL (or the netmask "
                    "0.0.0.0/0) and then explicitly specify to the hosts "
                    "allow parameter those hosts that should be permitted "
                    "access. Leave this field empty to use default settings"),
        blank=True,
    )
    rsyncmod_auxiliary = models.TextField(
        verbose_name=_("Auxiliary parameters"),
        help_text=_("These parameters will be added to the module "
                    "configuration in rsyncd.conf"),
        blank=True,
    )

    class Meta:
        verbose_name = _("Rsync Module")
        verbose_name_plural = _("Rsync Modules")
        ordering = ["rsyncmod_name"]

    class FreeAdmin:
        menu_child_of = 'services.Rsync'
        icon_model = u"rsyncModIcon"

    class Middleware:
        field_mapping = (
            ('id', 'id'),
            ('rsyncmod_name', 'name'),
            ('rsyncmod_comment', 'description'),
            ('rsyncmod_path', 'path'),
            ('rsyncmod_mode', 'mode'),
            ('rsyncmod_maxconn', 'max_connections'),
            ('rsyncmod_user', 'user'),
            ('rsyncmod_group', 'group'),
            ('rsyncmod_hostsallow', 'hosts_allow'),
            ('rsyncmod_hostsdeny', 'hosts_deny'),
            ('rsyncmod_auxiliary', 'auxiliary'),
        )
        provider_name = 'service.rsyncd.module'

    def __unicode__(self):
        return unicode(self.rsyncmod_name)


class SMART(NewModel):
    smart_interval = models.IntegerField(
        default=30,
        verbose_name=_("Check interval"),
        help_text=_("Sets the interval between disk checks to N minutes. "
                    "The default is 30 minutes"),
    )
    smart_powermode = models.CharField(
        choices=choices.SMART_POWERMODE,
        default="never",
        max_length=60,
        verbose_name=_("Power mode"),
    )
    smart_difference = models.IntegerField(
        default=0,
        verbose_name=_("Difference"),
        help_text=_("Report if the temperature had changed by at least N "
                    "degrees Celsius since last report. 0 to disable"),
    )
    smart_informational = models.IntegerField(
        default=0,
        verbose_name=_("Informational"),
        help_text=_("Report as informational in the system log if the "
                    "temperature is greater or equal than N degrees Celsius. "
                    "0 to disable"),
    )
    smart_critical = models.IntegerField(
        default=0,
        verbose_name=_("Critical"),
        help_text=_("Report as critical in the system log and send an "
                    "email if the temperature is greater or equal than N "
                    "degrees Celsius. 0 to disable"),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("S.M.A.R.T.")
        verbose_name_plural = _("S.M.A.R.T.")

    class FreeAdmin:
        deletable = False
        icon_model = u"SMARTIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('smart_interval', 'interval'),
            ('smart_powermode', 'power_mode'),
            ('smart_difference', 'temp_difference'),
            ('smart_informational', 'temp_informational'),
            ('smart_critical', 'temp_critical'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.smartd.get_config')
        return cls(**dict(
            id=1,
            smart_interval=config['interval'],
            smart_powermode=config['power_mode'],
            smart_difference=config['temp_difference'] or 0,
            smart_informational=config['temp_informational'] or 0,
            smart_critical=config['temp_critical'] or 0,
        ))

    def _save(self, *args, **kwargs):
        data = {
            'interval': self.smart_interval,
            'power_mode': self.smart_powermode,
            'temp_difference': self.smart_difference or None,
            'temp_informational': self.smart_informational or None,
            'temp_critical': self.smart_critical or None,
        }
        self._save_task_call('service.smartd.configure', data)
        return True


class RPCToken(Model):

    key = models.CharField(max_length=1024)
    secret = models.CharField(max_length=1024)

    @classmethod
    def new(cls):
        key = str(uuid.uuid4())
        h = hmac.HMAC(key=key, digestmod=hashlib.sha512)
        secret = str(h.hexdigest())
        instance = cls.objects.create(
            key=key,
            secret=secret,
            )
        return instance


class DomainController(Model):
    dc_realm = models.CharField(
        max_length=120,
        verbose_name=_("Realm"),
        help_text=_("Realm Name, eg EXAMPLE.ORG"),
    )
    dc_domain = models.CharField(
        max_length=120,
        verbose_name=_("Domain"),
        help_text=_("Domain Name in old format, eg EXAMPLE"),
    )
    dc_role = models.CharField(
        max_length=120,
        verbose_name=_("Server Role"),
        help_text=_("Server Role"),
        choices=choices.SAMBA4_ROLE_CHOICES,
        default='dc',
    )
    dc_dns_backend = models.CharField(
        max_length=120,
        verbose_name=_("DNS Backend"),
        help_text=_("DNS Backend, eg SAMBA_INTERNAL"),
        choices=choices.SAMBA4_DNS_BACKEND_CHOICES,
        default='SAMBA_INTERNAL',
    )
    dc_dns_forwarder = models.CharField(
        max_length=120,
        verbose_name=_("DNS Forwarder"),
        help_text=_("DNS Forwarder IP Address"),
    )
    dc_forest_level = models.CharField(
        max_length=120,
        verbose_name=_("Domain Forest Level"),
        help_text=_("Domain and Forest Level, eg 2003"),
        choices=choices.SAMBA4_FOREST_LEVEL_CHOICES,
        default='2003',
    )
    dc_passwd = models.CharField(
        max_length=120,
        verbose_name=_("Administrator Password"),
        help_text=_("Administrator Password"),
    )
    dc_kerberos_realm = models.ForeignKey(
        KerberosRealm,
        verbose_name=_("Kerberos Realm"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    def __init__(self, *args, **kwargs):
        super(DomainController, self).__init__(*args, **kwargs)
        self.svc = 'domaincontroller'

        if self.dc_passwd:
            self.dc_passwd = notifier().pwenc_decrypt(
                self.dc_passwd
            )
        self._dc_passwd_encrypted = False

    def save(self):

        if self.dc_passwd and not self._dc_passwd_encrypted:
            self.dc_passwd = notifier().pwenc_encrypt(
                self.dc_passwd
            )
            self._dc_passwd_encrypted = True

        super(DomainController, self).save()

        if not self.dc_kerberos_realm:
            try:
                from freenasUI.common.system import get_hostname

                hostname = get_hostname()
                dc_hostname = "%s.%s" % (hostname, self.dc_realm.lower())

                kr = KerberosRealm()
                kr.krb_realm = self.dc_realm.upper()
                kr.krb_kdc = dc_hostname
                kr.krb_admin_server = dc_hostname
                kr.krb_kpasswd_server = dc_hostname
                kr.save()

                self.dc_kerberos_realm = kr
                super(DomainController, self).save()

            except Exception as e:
                log.debug("DomainController: Unable to create kerberos realm: "
                          "%s", e)

    class Meta:
        verbose_name = _(u"Domain Controller")
        verbose_name_plural = _(u"Domain Controller")

    class FreeAdmin:
        deletable = False
        icon_model = u"DomainControllerIcon"


class WebDAV(NewModel):
    webdav_protocol = models.CharField(
        max_length=120,
        choices=choices.PROTOCOL_CHOICES,
        default="http",
        verbose_name=_("Protocol"),
    )

    webdav_tcpport = models.PositiveIntegerField(
        verbose_name=_("HTTP Port"),
        default=8080,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text=_("This is the port at which WebDAV will run on."
                    "<br>Do not use a port that is already in use by another "
                    "service (e.g. 22 for SSH)."),
    )

    webdav_tcpportssl = models.PositiveIntegerField(
        verbose_name=_("HTTPS Port"),
        default=8081,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text=_("This is the port at which Secure WebDAV will run on."
                    "<br>Do not use a port that is already in use by another "
                    "service (e.g. 22 for SSH)."),
    )

    webdav_password = models.CharField(
        max_length=120,
        verbose_name=_("Webdav Password"),
        default="davtest",
        help_text=_("The Default Password is: davtest"),
    )

    webdav_htauth = models.CharField(
        max_length=120,
        verbose_name=_("HTTP Authentication"),
        choices=choices.HTAUTH_CHOICES,
        default='digest',
        help_text=_("Type of HTTP Authentication for WebDAV"
                    "<br>Basic Auth: Password is sent over the network as "
                    "plaintext (Avoid if HTTPS is disabled) <br>Digest Auth: "
                    "Hash of the password is sent over the network (more "
                    "secure)"),
    )

    webdav_certssl = models.ForeignKey(
        Certificate,
        verbose_name=_("Webdav SSL Certificate"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _(u"WebDAV")
        verbose_name_plural = _(u"WebDAV")

    class FreeAdmin:
        deletable = False
        icon_model = u"WebDAVShareIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('webdav_protocol', 'protocol'),
            ('webdav_tcpport', 'http_port'),
            ('webdav_tcpportssl', 'https_port'),
            ('webdav_password', 'password'),
            ('webdav_htauth', 'authentication'),
            ('webdav_certssl', 'certificate'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.webdav.get_config')

        certificate = config['certificate']
        if certificate:
            try:
                certificate = Certificate.objects.get(pk=config['certificate'])
            except Certificate.DoesNotExist:
                certificate = None

        protocol = config.get('protocol', [])
        if 'HTTP' in protocol and 'HTTPS' in protocol:
            protocol = 'httphttps'
        elif 'HTTP' in protocol:
            protocol = 'http'
        elif 'HTTPS' in protocol:
            protocol = 'https'
        return cls(**dict(
            id=1,
            webdav_protocol=protocol,
            webdav_tcpport=config['http_port'],
            webdav_tcpportssl=config['https_port'],
            webdav_password=config['password'],
            webdav_htauth=config['authentication'],
            webdav_certssl=certificate,
        ))

    def _save(self, *args, **kwargs):
        if self.webdav_protocol == 'httphttps':
            protocol = ['HTTP', 'HTTPS']
        elif self.webdav_protocol == 'https':
            protocol = ['HTTPS']
        else:
            protocol = ['HTTP']

        data = {
            'protocol': protocol,
            'http_port': self.webdav_tcpport,
            'https_port': self.webdav_tcpportssl,
            'password': self.webdav_password,
            'authentication': self.webdav_htauth,
            'certificate': self.webdav_certssl.id if self.webdav_certssl else None,
        }
        self._save_task_call('service.webdav.configure', data)
        return True


class IPFS(NewModel):
    ipfs_path = PathField(
        verbose_name=_("Path"),
        blank=True,
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("IPFS")
        verbose_name_plural = _("IPFS")

    class FreeAdmin:
        deletable = False
        icon_model = u"IPFSIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('ipfs_path', 'path'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.ipfs.get_config')
        return cls(**dict(
            id=1,
            ipfs_path=config['path'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'path': self.ipfs_path or None,
        }
        self._save_task_call('service.ipfs.configure', data)
        return True

class Riak(NewModel):
    riak_nodename = models.CharField(
        verbose_name=_("Node Name"),
        max_length=200,
    )
    riak_nodeip = models.CharField(
        verbose_name=_("Node IP"),
        max_length=200,
    )
    riak_listener_http_internal = models.CharField(
        verbose_name=_("Listener HTTP Internal IP"),
        max_length=200,
    )
    riak_listener_http_internal_port = models.CharField(
        verbose_name=_("Listener HTTP Internal Port"),
        max_length=200,
    )
    riak_listener_https_internal = models.CharField(
        verbose_name=_("Listener HTTPS Internal IP"),
        max_length=200,
    )
    riak_listener_https_internal_port = models.CharField(
        verbose_name=_("Listener HTTPS Internal Port"),
        max_length=200,
    )
    riak_listener_protobuf_internal = models.CharField(
        verbose_name=_("Listener Protobuf Internal IP"),
        max_length=200,
    )
    riak_listener_protobuf_internal_port = models.CharField(
        verbose_name=_("Listener Protobuf Internal Port"),
        max_length=200,
    )
    riak_object_size_maximum = models.CharField(
        verbose_name=_("Object Size Max."),
        max_length=200,
    )
    riak_object_size_warning_threshold = models.CharField(
        verbose_name=_("Object Size Warning Threshold"),
        max_length=200,
    )
    riak_control = models.CharField(
        verbose_name=_("RIAK Control"),
        max_length=200,
    )
    riak_log_console_level = models.CharField(
        verbose_name=_("Log Level"),
        max_length=200,
        choices=(
            ('NONE', _('None')),
            ('DEBUG', _('Debug')),
            ('INFO', _('Info')),
            ('WARNING', _('Warning')),
            ('CRITICAL', _('Critical')),
            ('ALERT', _('Alert')),
            ('EMERGENCY', _('Emergency')),
            ('ERROR', _('Error')),
        ),
    )


    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("Riak KV")
        verbose_name_plural = _("Riak KV")

    class FreeAdmin:
        deletable = False
        icon_model = u"RIAKIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('riak_nodename', 'nodename'),
            ('riak_nodeip', 'node_ip'),
            ('riak_listener_http_internal', 'listener_http_internal'),
            ('riak_listener_http_internal_port', 'listener_http_internal_port'),
            ('riak_listener_https_internal', 'listener_https_internal'),
            ('riak_listener_https_internal_port', 'listener_https_internal_port'),
            ('riak_listener_protobuf_internal', 'listener_protobuf_internal'),
            ('riak_listener_protobuf_internal_port', 'listener_protobuf_internal_port'),
            ('riak_object_size_maximum', 'object_size_maximum'),
            ('riak_object_size_warning_threshold', 'object_size_warning_threshold'),
            ('riak_riak_control', 'riak_control'),
            ('riak_log_console', 'log_console'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.riak.get_config')
        return cls(**dict(
            id=1,
            riak_nodename=config['nodename'],
            riak_nodeip=config['node_ip'],
            riak_listener_http_internal=config['listener_http_internal'],
            riak_listener_http_internal_port=config['listener_http_internal_port'],
            riak_listener_https_internal=config['listener_https_internal'],
            riak_listener_https_internal_port=config['listener_https_internal_port'],
            riak_listener_protobuf_internal=config['listener_protobuf_internal'],
            riak_listener_protobuf_internal_port=config['listener_protobuf_internal_port'],
            riak_object_size_maximum=config['object_size_maximum'],
            riak_object_size_warning_threshold=config['object_size_warning_threshold'],
            riak_control=config['riak_control'],
            riak_log_console_level=config['log_console_level'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'nodename': self.riak_nodename,
            'node_ip': self.riak_nodeip,
            'listener_http_internal': self.riak_listener_http_internal,
            'listener_http_internal_port': self.riak_listener_http_internal_port,
            'listener_https_internal': self.riak_listener_https_internal,
            'listener_https_internal_port': self.riak_listener_https_internal_port,
            'listener_protobuf_internal': self.riak_listener_protobuf_internal,
            'listener_protobuf_internal_port': self.riak_listener_protobuf_internal_port,
            'object_size_maximum': self.riak_object_size_maximum,
            'object_size_warning_threshold': self.riak_object_size_warning_threshold,
            'riak_control': self.riak_riak_control,
            'log_console_level': self.riak_log_console_level,
        }
        self._save_task_call('service.riak.configure', data)
        return True


class Riak_CS(NewModel):
    riak_cs_nodename = models.CharField(
        verbose_name=_("Node Name"),
        max_length=200,
    )
    riak_cs_nodeip = models.CharField(
        verbose_name=_("Node IP"),
        max_length=200,
    )
    riak_cs_listener_ip = models.CharField(
        verbose_name=_("Listener Internal IP"),
        max_length=200,
    )
    riak_cs_listener_port = models.IntegerField(
        verbose_name=_("Listener Internal Port"),
    )
    riak_cs_riak_host_ip = models.CharField(
        verbose_name=_("RIAK KV Host IP"),
        max_length=200,
    )
    riak_cs_riak_host_port = models.IntegerField(
        verbose_name=_("RIAK KV Host Port"),
    )
    riak_cs_stanchion_host_ip = models.CharField(
        verbose_name=_("Stanchion Host IP"),
        max_length=200,
    )
    riak_cs_stanchion_host_port = models.IntegerField(
        verbose_name=_("Stanchion Host Port"),
    )
    riak_cs_anonymous_user_creation = models.BooleanField(
        verbose_name=_("Anonymous User Creation"),
        default=False,
    )
    riak_cs_admin_key = models.CharField(
        verbose_name=_("Admin Key"),
        max_length=200,
    )
    riak_cs_admin_secret = models.CharField(
        verbose_name=_("Admin Secret"),
        max_length=200,
    )
    riak_cs_max_buckets_per_user = models.IntegerField(
        verbose_name=_("Max Buckets per User"),
    )
    riak_cs_log_console_level = models.CharField(
        verbose_name=_("Log Level"),
        max_length=200,
        choices=(
            ('NONE', _('None')),
            ('DEBUG', _('Debug')),
            ('INFO', _('Info')),
            ('WARNING', _('Warning')),
            ('CRITICAL', _('Critical')),
            ('ALERT', _('Alert')),
            ('EMERGENCY', _('Emergency')),
            ('ERROR', _('Error')),
        ),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("Riak CS")
        verbose_name_plural = _("Riak CS")

    class FreeAdmin:
        deletable = False
        icon_model = u"RIAKCSIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('riak_cs_nodename', 'nodename'),
            ('riak_cs_nodeip', 'node_ip'),
            ('riak_cs_listener_ip', 'listener_ip'),
            ('riak_cs_listener_port', 'listener_port'),
            ('riak_cs_riak_host_ip', 'riak_host_ip'),
            ('riak_cs_riak_host_port', 'riak_host_port'),
            ('riak_cs_stanchion_host_ip', 'stanchion_host_ip'),
            ('riak_cs_stanchion_host_port', 'stanchion_host_port'),
            ('riak_cs_anonymous_user_creation', 'anonymous_user_creation'),
            ('riak_cs_admin_key', 'admin_key'),
            ('riak_cs_admin_secret', 'admin_secret'),
            ('riak_cs_max_buckets_per_user', 'max_buckets_per_user'),
            ('riak_cs_log_console_level', 'log_console_level'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.riak_cs.get_config')
        return cls(**dict(
            id=1,
            riak_cs_nodename=config['nodename'],
            riak_cs_nodeip=config['node_ip'],
            riak_cs_listener_ip=config['listener_ip'],
            riak_cs_listener_port=config['listener_port'],
            riak_cs_riak_host_ip=config['riak_host_ip'],
            riak_cs_riak_host_port=config['riak_host_port'],
            riak_cs_stanchion_host_ip=config['stanchion_host_ip'],
            riak_cs_stanchion_host_port=config['stanchion_host_port'],
            riak_cs_anonymous_user_creation=config['anonymous_user_creation'],
            riak_cs_admin_key=config['admin_key'],
            riak_cs_admin_secret=config['admin_secret'],
            riak_cs_max_buckets_per_user=config['max_buckets_per_user'],
            riak_cs_log_console_level=config['log_console_level'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'nodename': self.riak_cs_nodename,
            'node_ip': self.riak_cs_nodeip,
            'listener_ip': self.riak_cs_listener_ip,
            'listener_port': self.riak_cs_listener_port,
            'riak_host_ip': self.riak_cs_riak_host_ip,
            'riak_host_port': self.riak_cs_riak_host_port,
            'stanchion_host_ip': self.riak_cs_stanchion_host_ip,
            'stanchion_host_port': self.riak_cs_stanchion_host_port,
            'anonymous_user_creation': self.riak_cs_anonymous_user_creation,
            'admin_key': self.riak_cs_admin_key,
            'admin_secret': self.riak_cs_admin_secret,
            'max_buckets_per_user': self.riak_cs_max_buckets_per_user,
            'log_console_level': self.riak_cs_log_console_level,
        }
        self._save_task_call('service.riak_cs.configure', data)
        return True


class Stanchion(NewModel):
    stanchion_nodename = models.CharField(
        verbose_name=_("Node Name"),
        max_length=200,
    )
    stanchion_nodeip = models.CharField(
        verbose_name=_("Node IP"),
        max_length=200,
    )
    stanchion_listener_ip = models.CharField(
        verbose_name=_("Listener Internal IP"),
        max_length=200,
    )
    stanchion_listener_port = models.IntegerField(
        verbose_name=_("Listener Internal Port"),
    )
    stanchion_riak_host_ip = models.CharField(
        verbose_name=_("RIAK KV Host IP"),
        max_length=200,
    )
    stanchion_riak_host_port = models.IntegerField(
        verbose_name=_("RIAK KV Host Port"),
    )
    stanchion_admin_key = models.CharField(
        verbose_name=_("Admin Key"),
        max_length=200,
    )
    stanchion_admin_secret = models.CharField(
        verbose_name=_("Admin Secret"),
        max_length=200,
    )
    stanchion_log_console_level = models.CharField(
        verbose_name=_("Log Level"),
        max_length=200,
        choices=(
            ('NONE', _('None')),
            ('DEBUG', _('Debug')),
            ('INFO', _('Info')),
            ('WARNING', _('Warning')),
            ('CRITICAL', _('Critical')),
            ('ALERT', _('Alert')),
            ('EMERGENCY', _('Emergency')),
            ('ERROR', _('Error')),
        ),
    )


    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("Stanchion")
        verbose_name_plural = _("Stanchion")

    class FreeAdmin:
        deletable = False
        icon_model = u"STANCHIONIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('stanchion_nodename', 'nodename'),
            ('stanchion_nodeip', 'node_ip'),
            ('stanchion_listener_ip', 'listener_ip'),
            ('stanchion_listener_port', 'listener_port'),
            ('stanchion_riak_host_ip', 'riak_host_ip'),
            ('stanchion_riak_host_port', 'riak_host_port'),
            ('stanchion_admin_key', 'admin_key'),
            ('stanchion_admin_secret', 'admin_secret'),
            ('stanchion_log_console_level', 'log_console_level'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.stanchion.get_config')
        return cls(**dict(
            id=1,
            stanchion_nodename=config['nodename'],
            stanchion_nodeip=config['node_ip'],
            stanchion_listener_ip=config['listener_ip'],
            stanchion_listener_port=config['listener_port'],
            stanchion_riak_host_ip=config['riak_host_ip'],
            stanchion_riak_host_port=config['riak_host_port'],
            stanchion_admin_key=config['admin_key'],
            stanchion_admin_secret=config['admin_secret'],
            stanchion_log_console_level=config['log_console_level'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'nodename': self.stanchion_nodename,
            'node_ip': self.stanchion_nodeip,
            'listener_ip': self.stanchion_listener_ip,
            'listener_port': self.stanchion_listener_port,
            'riak_host_ip': self.stanchion_riak_host_ip,
            'riak_host_port': self.stanchion_riak_host_port,
            'admin_key': self.stanchion_admin_key,
            'admin_secret': self.stanchion_admin_secret,
            'log_console_level': self.stanchion_log_console_level,
        }
        self._save_task_call('service.stanchion.configure', data)
        return True


class HAProxy(NewModel):
    haproxy_global_maxconn = models.IntegerField(
        verbose_name=_("Global Max Connections"),
        max_length=200,
    )
    haproxy_defaults_maxconn = models.IntegerField(
        verbose_name=_("Default MAx Connections"),
        max_length=200,
    )
    haproxy_http_ip = models.CharField(
        verbose_name=_("Bind IP Address"),
        max_length=200,
    )
    haproxy_http_port = models.IntegerField(
        verbose_name=_("HTTP port"),
    )
    haproxy_https_ip = models.CharField(
        verbose_name=_("HTTPS IP"),
        max_length=200,
    )
    haproxy_https_port = models.IntegerField(
        verbose_name=_("HTTPS Port"),
    )
    haproxy_frontend_mode = models.CharField(
        verbose_name=_("Frontend Mode"),
        max_length=200,
        choices=(
            ('HTTP', _('HTTP')),
            ('TCP', _('TCP')),
        ),
    )
    haproxy_backend_mode = models.CharField(
        verbose_name=_("Backend Mode"),
        max_length=200,
        choices=(
            ('HTTP', _('HTTP')),
            ('TCP', _('TCP')),
        ),
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("HAProxy")
        verbose_name_plural = _("HAProxy")

    class FreeAdmin:
        deletable = False
        icon_model = u"HAPROXYIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('haproxy_global_maxconn', 'global_maxconn'),
            ('haproxy_defaults_maxconn', 'defaults_maxconn'),
            ('haproxy_http_ip', 'http_ip'),
            ('haproxy_http_port', 'http_port'),
            ('haproxy_https_ip', 'https_ip'),
            ('haproxy_https_port', 'https_port'),
            ('haproxy_frontend_mode', 'frontend_mode'),
            ('haproxy_backend_mode', 'backend_mode'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.haproxy.get_config')
        return cls(**dict(
            id=1,
            haproxy_global_maxconn=config['global_maxconn'],
            haproxy_defaults_maxconn=config['defaults_maxconn'],
            haproxy_http_ip=config['http_ip'],
            haproxy_http_port=config['http_port'],
            haproxy_https_ip=config['https_ip'],
            haproxy_https_port=config['https_port'],
            haproxy_frontend_mode=config['frontend_mode'],
            haproxy_backend_mode=config['backend_mode'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'global_maxconn': self.haproxy_global_maxconn,
            'defaults_maxconn': self.haproxy_defaults_maxconn,
            'http_ip': self.haproxy_http_ip,
            'http_port': self.haproxy_http_port,
            'https_ip': self.haproxy_https_ip,
            'https_port': self.haproxy_https_port,
            'frontend_mode': self.haproxy_frontend_mode,
            'backend_mode': self.haproxy_backend_mode,
        }
        self._save_task_call('service.haproxy.configure', data)
        return True


class Glusterd(NewModel):
    glusterd_working_directory = models.CharField(
        verbose_name=_("Database Directory"),
        max_length=200,
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("Glusterd")
        verbose_name_plural = _("Glusterd")

    class FreeAdmin:
        deletable = False
        icon_model = u"GLUSTERDIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('glusterd_working_directory', 'working_directory'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.glusterd.get_config')
        return cls(**dict(
            id=1,
            glusterd_working_directory=config['working_directory'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'working_directory': self.glusterd_working_directory,
        }
        self._save_task_call('service.glusterd.configure', data)
        return True

class SWIFT(NewModel):
    swift_swift_hash_path_suffix = models.CharField(
        verbose_name=_("Database Directory"),
        max_length=200,
    )
    swift_swift_hash_path_prefix = models.CharField(
        verbose_name=_("Database Directory"),
        max_length=200,
    )

    objects = NewManager(qs_class=ConfigQuerySet)

    class Meta:
        verbose_name = _("SWIFT")
        verbose_name_plural = _("SWIFT")

    class FreeAdmin:
        deletable = False
        icon_model = u"SWIFTIcon"

    class Middleware:
        configstore = True
        field_mapping = (
            ('swift_swift_hash_path_suffix', 'swift_hash_path_suffix'),
            ('swift_swift_hash_path_prefix', 'swift_hash_path_prefix'),
        )

    @classmethod
    def _load(cls):
        from freenasUI.middleware.connector import connection as dispatcher
        config = dispatcher.call_sync('service.swift.get_config')
        return cls(**dict(
            id=1,
            swift_swift_hash_path_suffix=config['swift_hash_path_suffix'],
            swift_swift_hash_path_prefix=config['swift_hash_path_prefix'],
        ))

    def _save(self, *args, **kwargs):
        data = {
            'swift_hash_path_suffix': self.swift_swift_hash_path_suffix,
            'swift_hash_path_prefix': self.swift_swift_hash_path_prefix,
        }
        self._save_task_call('service.swift.configure', data)
        return True
