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

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.freeadmin.models import Model, UserField, GroupField, PathField
from freenasUI.freeadmin.models.fields import MultiSelectField
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Task


class CIFS_Share(Model):
    cifs_path = PathField(
        verbose_name=_("Path"),
        blank=True,
    )
    cifs_home = models.BooleanField(
        verbose_name=_('Use as home share'),
        default=False,
    )
    cifs_name = models.CharField(
        max_length=120,
        verbose_name=_("Name")
    )
    cifs_comment = models.CharField(
        max_length=120,
        verbose_name=_("Comment"),
        blank=True,
    )
    cifs_default_permissions = models.BooleanField(
        verbose_name=_('Apply Default Permissions'),
        help_text=_('Recursively set sane default windows permissions on share'),
        default=True
    )
    cifs_ro = models.BooleanField(
        verbose_name=_('Export Read Only'),
        default=False,
    )
    cifs_browsable = models.BooleanField(
        verbose_name=_('Browsable to Network Clients'),
        default=True,
    )
    cifs_recyclebin = models.BooleanField(
        verbose_name=_('Export Recycle Bin'),
        default=False,
    )
    cifs_showhiddenfiles = models.BooleanField(
        verbose_name=_('Show Hidden Files'),
        default=False,
    )
    cifs_guestok = models.BooleanField(
        verbose_name=_('Allow Guest Access'),
        help_text=_(
            'If true then no password is required to connect to the share. '
            'Privileges will be those of the guest account.'
        ),
        default=False,
    )
    cifs_guestonly = models.BooleanField(
        verbose_name=_('Only Allow Guest Access'),
        help_text=_(
            'If true then only guest connections to the share are permitted. '
            'This parameter will have no effect if Allow Guest Access is not '
            'set for the share.'
        ),
        default=False,
    )
    cifs_hostsallow = models.TextField(
        blank=True,
        verbose_name=_("Hosts Allow"),
        help_text=_(
            "This option is a comma, space, or tab delimited set of hosts "
            "which are permitted to access this share. You can specify the "
            "hosts by name or IP number. Leave this field empty to use "
            "default settings."
        ),
    )
    cifs_hostsdeny = models.TextField(
        blank=True,
        verbose_name=_("Hosts Deny"),
        help_text=_(
            "This option is a comma, space, or tab delimited set of host "
            "which are NOT permitted to access this share. Where the lists "
            "conflict, the allow list takes precedence. In the event that it "
            "is necessary to deny all by default, use the keyword ALL (or the "
            "netmask 0.0.0.0/0) and then explicitly specify to the hosts "
            "allow parameter those hosts that should be permitted access. "
            "Leave this field empty to use default settings."
        ),
    )
    cifs_vfsobjects = MultiSelectField(
        verbose_name=_('VFS Objects'),
        max_length=255,
        blank=True,
        default='streams_xattr,aio_pthread',
        choices=list(choices.CIFS_VFS_OBJECTS())
    )
    cifs_storage_task = models.ForeignKey(
        Task,
        verbose_name=_("Periodic Snapshot Task"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    cifs_auxsmbconf = models.TextField(
        max_length=120,
        verbose_name=_("Auxiliary Parameters"),
        blank=True,
        help_text=_("These parameters are added to [Share] section of smb.conf")
    )

    def __str__(self):
        return self.cifs_name

    def delete(self, *args, **kwargs):
        super(CIFS_Share, self).delete(*args, **kwargs)
        notifier().reload("cifs")

    class Meta:
        verbose_name = _("Windows (SMB) Share")
        verbose_name_plural = _("Windows (SMB) Shares")
        ordering = ["cifs_name"]


class AFP_Share(Model):
    afp_path = PathField(
        verbose_name=_("Path"),
    )
    afp_name = models.CharField(
        max_length=120,
        verbose_name=_("Name"),
        help_text=_(
            "The volume name is the name that appears in the Chooser of the "
            "'connect to server' dialog on Macintoshes to represent the "
            "appropriate share. If volumename is unspecified, the last "
            "component of pathname is used. No two volumes may have the same "
            "name. The volume name cannot contain the ':' character. The "
            "volume name is mangled if it is very long. Mac codepage volume "
            "name is limited to 27 characters. UTF8-MAC volume name is limited"
            " to 'Volume Name Length' parameter in Services:Apple Share"
        ),
    )
    afp_comment = models.CharField(
        max_length=120,
        verbose_name=_("Share Comment"),
        blank=True
    )
    afp_allow = models.CharField(
        max_length=120,
        verbose_name=_("Allow List"),
        blank=True,
        help_text=_(
            "This option allows the users and groups that access a share to "
            "be specified. Users and groups are specified, delimited by "
            "commas. Groups are designated by a @ prefix."
        ),
    )
    afp_deny = models.CharField(
        max_length=120,
        verbose_name=_("Deny List"),
        blank=True,
        help_text=_(
            "The deny option specifies users and groups who are not allowed "
            "access to the share. It follows the same format as the allow "
            "option."
        ),
    )
    afp_ro = models.CharField(
        max_length=120,
        verbose_name=_("Read-only Access"),
        blank=True,
        help_text=_(
            "Allows certain users and groups to have read-only access to a "
            "share. This follows the allow option format."
        ),
    )
    afp_rw = models.CharField(
        max_length=120,
        verbose_name=_("Read-write Access"),
        blank=True,
        help_text=_(
            "Allows certain users and groups to have read/write access to a "
            "share. This follows the allow option format."
        ),
    )
    afp_timemachine = models.BooleanField(
        verbose_name=_('Time Machine'),
        help_text=_(
            'Check this to enable Time Machine backups on this share.'
        ),
        default=False,
    )
    afp_nodev = models.BooleanField(
        verbose_name=_('Zero Device Numbers'),
        help_text=_(
            'Always use 0 for device number, helps when the device number is '
            'not constant across a reboot, cluster, ...'
        ),
        default=False,
    )
    afp_nostat = models.BooleanField(
        verbose_name=_('No Stat'),
        help_text=_(
            'Don\'t stat volume path when enumerating volumes list, useful '
            'for automounting or volumes created by a preexec script.'
        ),
        default=False,
    )
    afp_upriv = models.BooleanField(
        verbose_name=_('AFP3 Unix Privs'),
        help_text=_('Use AFP3 unix privileges.'),
        default=True,
    )
    afp_fperm = models.CharField(
        max_length=3,
        default="644",
        verbose_name=_("Default file permission"),
    )
    afp_dperm = models.CharField(
        max_length=3,
        default="755",
        verbose_name=_("Default directory permission"),
    )
    afp_umask = models.CharField(
        max_length=3,
        default="000",
        blank=True,
        verbose_name=_("Default umask"),
    )
    afp_hostsallow = models.CharField(
        blank=True,
        max_length=120,
        help_text=_(
            "Allow only listed hosts and/or networks access to this volume"
        ),
        verbose_name=_("Hosts Allow")
    )
    afp_hostsdeny = models.CharField(
        blank=True,
        max_length=120,
        help_text=_("Deny listed hosts and/or networks access to this volume"),
        verbose_name=_("Hosts Deny")
    )

    afp_auxparams = models.TextField(
        blank=True,
        max_length=255,
        help_text=_(
            "These parameters are added to the [Volume] section of afp.conf."
            " Add each different parameter on a newline"
        ),
        verbose_name=_("Auxiliary Parameters")
    )

    def __str__(self):
        return str(self.afp_name)

    def delete(self, *args, **kwargs):
        super(AFP_Share, self).delete(*args, **kwargs)
        notifier().reload("afp")

    class Meta:
        verbose_name = _("Apple (AFP) Share")
        verbose_name_plural = _("Apple (AFP) Shares")
        ordering = ["afp_name"]


class NFS_Share(Model):
    nfs_comment = models.CharField(
        max_length=120,
        verbose_name=_("Comment"),
        blank=True,
    )
    nfs_network = models.TextField(
        verbose_name=_("Authorized networks"),
        help_text=_(
            "Networks that are authorized to access the NFS share."
            " Specify network numbers of the form 1.2.3.4/xx where xx is "
            "the number of bits of netmask."
        ),
        blank=True,
    )
    nfs_hosts = models.TextField(
        verbose_name=_("Authorized IP addresses or hosts"),
        help_text=_(
            "IP addresses or hostnames that are authorized to "
            "access the NFS share."
        ),
        blank=True,
    )
    nfs_alldirs = models.BooleanField(
        verbose_name=_('All Directories'),
        help_text=_(
            'Allow mounting of any subdirectory under this mount point if'
            'selected. Otherwise, only the top level directory can be mounted.'
        ),
        default=False,
    )
    nfs_ro = models.BooleanField(
        verbose_name=_('Read Only'),
        help_text=_('Export the share read only. Writes are not permitted.'),
        default=False,
    )
    nfs_quiet = models.BooleanField(
        verbose_name=_('Quiet'),
        help_text=_(
            'Inhibit syslog warnings if there are problems with exporting '
            'this share.'
        ),
        default=False,
    )
    nfs_maproot_user = UserField(
        verbose_name=_("Maproot User"),
        max_length=120,
        blank=True,
        null=True,
        default='',
        help_text=_(
            "The credentials of the specified user is used for remote access "
            "by root."
        ),
    )
    nfs_maproot_group = GroupField(
        verbose_name=_("Maproot Group"),
        max_length=120,
        blank=True,
        null=True,
        default='',
        help_text=_(
            "The credentials of the specified group is used for remote access "
            "by root."
        ),
    )
    nfs_mapall_user = UserField(
        verbose_name=_("Mapall User"),
        max_length=120,
        blank=True,
        null=True,
        default='',
        help_text=_(
            "The credentials of the specified user is used for remote access "
            "by all users."
        ),
    )
    nfs_mapall_group = GroupField(
        verbose_name=_("Mapall Group"),
        max_length=120,
        blank=True,
        null=True,
        default='',
        help_text=_(
            "The credentials of the specified group is used for remote access "
            "by all users."
        ),
    )
    nfs_security = MultiSelectField(
        verbose_name=_('Security'),
        max_length=200,
        blank=True,
        choices=(
            ('sys', 'sys'),
            ('krb5', 'krb5'),
            ('krb5i', 'krb5i'),
            ('krb5p', 'krb5p'),
        ),
    )

    def __str__(self):
        if self.nfs_comment:
            return str(self.nfs_comment)
        return "[%s]" % ', '.join([p.path for p in self.paths.all()])

    def delete(self, *args, **kwargs):
        super(NFS_Share, self).delete(*args, **kwargs)
        notifier().reload("nfs")

    @property
    def nfs_paths(self):
        return [p.path for p in self.paths.all()]

    class Meta:
        verbose_name = _("Unix (NFS) Share")
        verbose_name_plural = _("Unix (NFS) Shares")


class NFS_Share_Path(Model):
    share = models.ForeignKey(NFS_Share, related_name="paths")
    path = PathField(verbose_name=_("Path"))

    def __str__(self):
        return self.path

    class Meta:
        verbose_name = _("Path")
        verbose_name_plural = _("Paths")
        ordering = ["path"]


class WebDAV_Share(Model):
    webdav_name = models.CharField(
        max_length=120,
        verbose_name=_("Share Name"),
        help_text=_(
            "This will be used to access your WebDAV share.<br />For example "
            "http(s)://ip-of-freenas-machine:webdav_port/'Share Name'"
        ),
    )
    webdav_comment = models.CharField(
        max_length=120,
        verbose_name=_("Comment"),
        blank=True,
    )
    webdav_path = PathField(
        verbose_name=_("Path")
    )
    webdav_ro = models.BooleanField(
        verbose_name=_('Read Only'),
        help_text=_('Export the share read only. Writes are not permitted.'),
        default=False,
    )
    webdav_perm = models.BooleanField(
        verbose_name=_('Change User & Group Ownership'),
        help_text=_(
            "Changes the user & group of the shared folder"
            " to 'webdav:webdav' recursively (including all subdirectories)"
            "<br />If disabled, you will need to manually"
            "<br />add the 'webdav' user & group to the share."
        ),
        default=True,
    )

    def __str__(self):
        return self.webdav_name

    def delete(self, *args, **kwargs):
        super(WebDAV_Share, self).delete(*args, **kwargs)
        notifier().reload("webdav")

    class Meta:
        verbose_name = _("WebDAV Share")
        verbose_name_plural = _("WebDAV Shares")
        ordering = ["webdav_name"]
