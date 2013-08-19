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
from freenasUI.freeadmin.models import Model, UserField, GroupField, PathField
from freenasUI.middleware.notifier import notifier


class CIFS_Share(Model):
    cifs_name = models.CharField(
            max_length=120,
            verbose_name=_("Name")
            )
    cifs_comment = models.CharField(
            max_length=120,
            verbose_name=_("Comment"),
            blank=True,
            )
    cifs_path = PathField(
            verbose_name=_("Path"))
    cifs_ro = models.BooleanField(
            verbose_name=_("Export Read Only"))
    cifs_browsable = models.BooleanField(
            verbose_name=_("Browsable to Network Clients"), default=True)
    cifs_inheritowner = models.BooleanField(
            verbose_name=_("Inherit Owner"), default=False)
    cifs_inheritperms = models.BooleanField(
            verbose_name=_("Inherit Permissions"))
    cifs_recyclebin = models.BooleanField(
            verbose_name=_("Export Recycle Bin"))
    cifs_showhiddenfiles = models.BooleanField(
            verbose_name=_("Show Hidden Files"))
    cifs_guestok = models.BooleanField(
            verbose_name=_("Allow Guest Access"),
            help_text=_("If true then no password is required to connect to "
                "the share. Privileges will be those of the guest account."))
    cifs_guestonly = models.BooleanField(
            verbose_name=_("Only Allow Guest Access"),
            help_text=_("If true then only guest connections to the share "
                "are permitted. This parameter will have no effect if Allow "
                "Guest Access is not set for the share."))
    cifs_hostsallow = models.TextField(
            blank=True,
            verbose_name=_("Hosts Allow"),
            help_text=_("This option is a comma, space, or tab delimited set of hosts which are permitted to access this share. You can specify the hosts by name or IP number. Leave this field empty to use default settings.")
            )
    cifs_hostsdeny = models.TextField(
            blank=True,
            verbose_name=_("Hosts Deny"),
            help_text=_("This option is a comma, space, or tab delimited set of host which are NOT permitted to access this share. Where the lists conflict, the allow list takes precedence. In the event that it is necessary to deny all by default, use the keyword ALL (or the netmask 0.0.0.0/0) and then explicitly specify to the hosts allow parameter those hosts that should be permitted access. Leave this field empty to use default settings.")
            )
    cifs_auxsmbconf = models.TextField(
            max_length=120,
            verbose_name=_("Auxiliary Parameters"),
            blank=True,
            help_text=_("These parameters are added to [Share] section of smb.conf")
            )

    def __unicode__(self):
        return self.cifs_name

    def delete(self, *args, **kwargs):
        super(CIFS_Share, self).delete(*args, **kwargs)
        notifier().reload("cifs")

    class Meta:
        verbose_name = _("Windows (CIFS) Share")
        verbose_name_plural = _("Windows (CIFS) Shares")
        ordering = ["cifs_name"]


class AFP_Share(Model):
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
    afp_path = PathField(
            verbose_name=_("Path"))
    afp_sharepw = models.CharField(
            max_length=120,
            verbose_name=_("Share password"),
            blank=True,
            help_text=_("This option allows you to set a volume password, which can be a maximum of 8 characters long (using ASCII strongly recommended at the time of this writing).")
        )
    afp_sharecharset = models.CharField(
            max_length=120,
            verbose_name=_("Share Character Set"),
            blank=True,
            help_text=_("Specifies the share character set. For example UTF8, UTF8-MAC, ISO-8859-15, etc.")
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
    afp_diskdiscovery = models.BooleanField(
            verbose_name=_("Disk Discovery"),
            help_text=_("Allow other systems to discover this share as a disk for data, as a Time Machine backup volume or not at all.")
            )
    afp_discoverymode = models.CharField(
            max_length=120,
            choices=choices.DISKDISCOVERY_CHOICES,
            default='default',
            verbose_name=_("Disk discovery mode"),
            help_text=_("Note! Selecting 'Time Machine' on multiple shares may cause unpredictable behavior in MacOS. Default mode exports the volume as a data volume for users.")
            )
    afp_dbpath = models.CharField(
            max_length=120,
            verbose_name=_("Database Path"),
            blank=True,
            help_text=_("Sets the database information to be stored in path. You have to specify a writable location, even if the volume is read only.")
            )
    afp_cachecnid = models.BooleanField(
            verbose_name=_("Cache CNID"),
            help_text=_("If set afpd uses the ID information stored in AppleDouble V2 header files to reduce database load. Don't set this option if the volume is modified by non AFP clients (NFS/SMB/local).")
            )
    afp_crlf = models.BooleanField(
            verbose_name=_("Translate CR/LF"),
            help_text=_("Enables crlf translation for TEXT files, automatically converting macintosh line breaks into Unix ones. Use of this option might be dangerous since some older programs store binary data files as type 'TEXT' when saving and switch the filetype in a second step. Afpd will potentially destroy such files when 'erroneously' changing bytes in order to do line break translation.")
            )
    afp_mswindows = models.BooleanField(
            verbose_name=_("Windows File Names"),
            help_text=_("This forces filenames to be restricted to the character set used by Windows. This is not recommended for shares used principally by Mac computers.")
            )
    afp_adouble = models.BooleanField(
            verbose_name=_("Enable .AppleDouble"),
            help_text=_("This will enable automatic creation of the "
                ".AppleDouble directories. This option should be used if "
                "files are accessed by Mac computers."),
            default=True,
            )
    afp_nodev = models.BooleanField(
            verbose_name=_("Zero Device Numbers"),
            help_text=_("Always use 0 for device number, helps when the device number is not constant across a reboot, cluster, ...")
            )
    afp_nofileid = models.BooleanField(
            verbose_name=_("Disable File ID"),
            help_text=_("Don't advertise createfileid, resolveid, deleteid calls.")
            )
    afp_nohex = models.BooleanField(
            verbose_name=_("Disable :hex Names"),
            help_text=_("Disable :hex translations for anything except dot files. This option makes the '/' character illegal.")
            )
    afp_prodos = models.BooleanField(
            verbose_name=_("ProDOS"),
            help_text=_("Provide compatibility with Apple II clients.")
            )
    afp_nostat = models.BooleanField(
            verbose_name=_("No Stat"),
            help_text=_("Don't stat volume path when enumerating volumes list, useful for automounting or volumes created by a preexec script.")
            )
    afp_upriv = models.BooleanField(
            verbose_name=_("AFP3 Unix Privs"),
            default=True,
            help_text=_("Use AFP3 unix privileges.")
            )
    afp_fperm = models.CharField(
            max_length=3,
            default="755",
            verbose_name=_("Default file permission"),
            )
    afp_dperm = models.CharField(
            max_length=3,
            default="644",
            verbose_name=_("Default directory permission"),
            )

    def __unicode__(self):
        return unicode(self.afp_name)

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
            help_text=_("Networks that are authorized to access the NFS share."
                " Specify network numbers of the form 1.2.3.4/xx where xx is "
                "the number of bits of netmask."),
            blank=True,
            )
    nfs_hosts = models.TextField(
            verbose_name=_("Authorized IP addresses or hosts"),
            help_text=_("IP addresses or hostnames that are authorized to "
                "access the NFS share."),
            blank=True,
            )
    nfs_alldirs = models.BooleanField(
            verbose_name=_("All Directories"),
            help_text=_("Allow mounting of any subdirectory under this mount point if selected. Otherwise, only the top level directory can be mounted."),
            )
    nfs_ro = models.BooleanField(
            verbose_name=_("Read Only"),
            help_text=_("Export the share read only. Writes are not permitted.")
            )
    nfs_quiet = models.BooleanField(
            verbose_name=_("Quiet"),
            help_text=_("Inhibit syslog warnings if there are problems with exporting this share.")
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

    def __unicode__(self):
        if self.nfs_comment:
            return unicode(self.nfs_comment)
        return u"[%s]" % ', '.join([p.path for p in self.paths.all()])

    def delete(self, *args, **kwargs):
        super(NFS_Share, self).delete(*args, **kwargs)
        notifier().reload("nfs")

    @property
    def nfs_paths(self):
        return [p.path for p in self.paths.all()]

    class Meta:
        verbose_name = _("Unix (NFS) Share")
        verbose_name_plural = _("Unix (NFS) Shares")
        #ordering = ["nfs_path"]


class NFS_Share_Path(Model):
    share = models.ForeignKey(NFS_Share, related_name="paths")
    path = PathField(
            verbose_name=_("Path"))

    def __unicode__(self):
        return self.path

    class Meta:
        verbose_name = _("Path")
        verbose_name_plural = _("Paths")
