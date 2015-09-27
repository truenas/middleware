#+
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
from freenasUI.freeadmin.models import Model, NewModel, UserField, GroupField, PathField
from freenasUI.freeadmin.models.fields import MultiSelectField
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Task


class CIFS_Share(NewModel):
    id = models.CharField(
        max_length=120,
        primary_key=True
    )
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
            default=""
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

    #cifs_storage_task = models.ForeignKey(
    #    Task,
    #    verbose_name=_("Periodic Snapshot Task"),
    #    on_delete=models.SET_NULL,
    #    blank=True,
    #    null=True
    #)

    def __unicode__(self):
        return self.cifs_name

    def delete(self, *args, **kwargs):
        super(CIFS_Share, self).delete(*args, **kwargs)
        notifier().reload("cifs")

    class Meta:
        verbose_name = _("Windows (CIFS) Share")
        verbose_name_plural = _("Windows (CIFS) Shares")
        ordering = ["cifs_name"]

    class Middleware:
        middleware_methods = {
            'query': 'shares.query',
            'add': 'share.create',
            'update': 'share.update',
            'delete': 'share.delete'
        }
        default_filters = [
            ('type', '=', 'cifs')
        ]
        field_mapping = (
            (('id', 'cifs_name'), 'id'),
            ('cifs_path', 'target'),
            ('cifs_comment', 'description'),
            ('cifs_ro', 'properties.read_only'),
            ('cifs_browsable', 'properties.browseable'),
            ('cifs_recyclebin', 'properties.recyclebin'),
            ('cifs_showhiddenfiles', 'properties.show_hidden_files'),
            ('cifs_guestok', 'properties.guest_ok'),
            ('cifs_guestonly', 'properties.guest_only'),
        )
        extra_fields = (
            ('type', 'cifs'),
        )


class AFP_Share(NewModel):
    id = models.CharField(
        max_length=120,
        primary_key=True
    )
    afp_path = PathField(
        verbose_name=_("Path"),
    )
    afp_name = models.CharField(
            max_length=120,
            verbose_name=_("Name"),
            help_text=_("The volume name is the name that appears in the Chooser of the 'connect to server' dialog on Macintoshes to represent the appropriate share. If volumename is unspecified, the last component of pathname is used. No two volumes may have the same name. The volume name cannot contain the ':' character. The volume name is mangled if it is very long. Mac codepage volume name is limited to 27 characters. UTF8-MAC volume name is limited to 'Volume Name Length' parameter in Services:Apple Share")
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
            help_text=_("This option allows the users and groups that access a share to be specified. Users and groups are specified, delimited by commas. Groups are designated by a @ prefix.")
            )
    afp_deny = models.CharField(
            max_length=120,
            verbose_name=_("Deny List"),
            blank=True,
            help_text=_("The deny option specifies users and groups who are not allowed access to the share. It follows the same format as the allow option.")
            )
    afp_ro = models.CharField(
            max_length=120,
            verbose_name=_("Read-only Access"),
            blank=True,
            help_text=_("Allows certain users and groups to have read-only access to a share. This follows the allow option format.")
        )
    afp_rw = models.CharField(
            max_length=120,
            verbose_name=_("Read-write Access"),
            blank=True,
            help_text=_("Allows certain users and groups to have read/write access to a share. This follows the allow option format.")
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
        help_text=_("Allow only listed hosts and/or networks access to this volume"),
        verbose_name=_("Hosts Allow")
        )
    afp_hostsdeny = models.CharField(
        blank=True,
        max_length=120,
        help_text=_("Deny listed hosts and/or networks access to this volume"),
        verbose_name=_("Hosts Deny")
        )

    def __unicode__(self):
        return unicode(self.afp_name)

    class Meta:
        verbose_name = _("Apple (AFP) Share")
        verbose_name_plural = _("Apple (AFP) Shares")
        ordering = ["afp_name"]

    class Middleware:
        middleware_methods = {
            'query': 'shares.query',
            'add': 'share.create',
            'update': 'share.update',
            'delete': 'share.delete'
        }
        default_filters = [
            ('type', '=', 'afp')
        ]
        field_mapping = (
            (('id', 'afp_name'), 'id'),
            ('afp_comment', 'description'),
            ('afp_timemachine', 'properties.time_machine'),
            ('afp_nodev', 'properties.zero_dev_numbers'),
            ('afp_nostat', 'properties.no_stat'),
            ('afp_upriv', 'properties.afp3_privileges'),
            ('afp_fperm', 'properties.default_file_perms'),
            ('afp_dperm', 'properties.default_directory_perms'),
            ('afp_umask', 'properties.default_umask')
        )
        extra_fields = (
            ('type', 'afp'),
        )


class NFS_Share(NewModel):
    id = models.CharField(
        max_length=120,
        primary_key=True
    )
    nfs_name = models.CharField(
        max_length=120,
        verbose_name=_("Share name")
    )
    nfs_path = models.CharField(
            max_length=255,
            verbose_name=_("Path"),
            blank=True,
            )
    nfs_comment = models.CharField(
            max_length=120,
            verbose_name=_("Comment"),
            blank=True,
            )
    nfs_hosts = models.TextField(
            verbose_name=_("Authorized IP addresses or hosts"),
            help_text=_("IP addresses or hostnames that are authorized to "
                "access the NFS share."),
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
    nfs_maproot_user = UserField(
            verbose_name=_("Maproot User"),
            max_length=120,
            blank=True,
            null=True,
            default='',
            help_text=_("If a user is selected, the root user is limited to "
                "that user's permissions")
            )
    nfs_maproot_group = GroupField(
            verbose_name=_("Maproot Group"),
            max_length=120,
            blank=True,
            null=True,
            default='',
            help_text=_("If a group is selected, the root user will also be "
                "limited to that group's permissions")
            )
    nfs_mapall_user = UserField(
            verbose_name=_("Mapall User"),
            max_length=120,
            blank=True,
            null=True,
            default='',
            help_text=_("The specified user's permissions are used by all "
                "clients")
            )
    nfs_mapall_group = GroupField(
            verbose_name=_("Mapall Group"),
            max_length=120,
            blank=True,
            null=True,
            default='',
            help_text=_("The specified group's permission are used by all "
                "clients")
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

    def __unicode__(self):
        return self.nfs_name

    class Meta:
        verbose_name = _("Unix (NFS) Share")
        verbose_name_plural = _("Unix (NFS) Shares")

    class Middleware:
        middleware_methods = {
            'query': 'shares.query',
            'add': 'share.create',
            'update': 'share.update',
            'delete': 'share.delete'
        }
        default_filters = [
            ('type', '=', 'nfs')
        ]
        field_mapping = (
            (('id', 'nfs_name'), 'id'),
            ('nfs_comment', 'description'),
            ('nfs_path', 'target'),
            ('nfs_alldirs', 'properties.alldirs'),
            ('nfs_ro', 'properties.read_only'),
            ('nfs_maproot_user', 'properties.maproot_user'),
            ('nfs_maproot_group', 'properties.maproot_group'),
            ('nfs_mapall_user', 'properties.mapall_user'),
            ('nfs_mapall_group', 'properties.mapall_group'),
        )
        extra_fields = (
            ('type', 'nfs'),
        )



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

    def __unicode__(self):
      return self.webdav_name

    def delete(self, *args, **kwargs):
        super(WebDAV_Share, self).delete(*args, **kwargs)
        notifier().reload("webdav")

    class Meta:
        verbose_name = _("WebDAV Share")
        verbose_name_plural = _("WebDAV Shares")
        ordering = ["webdav_name"]
