#+
# Copyright 2010 iXsystems
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
# $FreeBSD$
#####################################################################

from django.db import models
from django.utils.translation import ugettext_lazy as _

from storage.models import MountPoint as MountPoint 
from freenasUI import choices
from freeadmin.models import Model, UserField, GroupField

mountpoint_limiter = { 'mp_path__startswith': '/mnt/' }

class CIFS_Share(Model):
    cifs_name = models.CharField(
            max_length=120, 
            verbose_name = _("Name")
            )
    cifs_comment = models.CharField(
            max_length=120, 
            verbose_name = _("Comment"),
            blank=True,
            )
    cifs_path = models.ForeignKey(MountPoint, limit_choices_to=mountpoint_limiter,
            verbose_name = _("Path"))
    cifs_ro = models.BooleanField(
            verbose_name = _("Export Read Only"))
    cifs_browsable = models.BooleanField(
            verbose_name = _("Browsable to Network Clients"), default=True)
    cifs_inheritperms = models.BooleanField(
            verbose_name = _("Inherit Permissions"))
    cifs_recyclebin = models.BooleanField(
            verbose_name = _("Export Recycle Bin"))
    cifs_showhiddenfiles = models.BooleanField(
            verbose_name = _("Show Hidden Files"))
    cifs_guest = UserField(
            max_length=120, 
            default="www", 
            verbose_name = _("Guest Account"), 
            help_text = _("Use this option to override the username ('ftp' by default) which will be used for access to services which are specified as guest. Whatever privileges this user has will be available to any client connecting to the guest service. This user must exist in the password file, but does not require a valid login.")
            )
    cifs_guestok = models.BooleanField(
            verbose_name = _("Allow Guest Access"))
    cifs_guestonly = models.BooleanField(
            verbose_name = _("Only Allow Guest Access"))
    cifs_hostsallow = models.CharField(
            max_length=120, 
            blank=True, 
            verbose_name = _("Hosts Allow"),
            help_text = _("This option is a comma, space, or tab delimited set of hosts which are permitted to access this share. You can specify the hosts by name or IP number. Leave this field empty to use default settings.")
            )
    cifs_hostsdeny = models.CharField(
            max_length=120, 
            blank=True, 
            verbose_name = _("Hosts Deny"),
            help_text = _("This option is a comma, space, or tab delimited set of host which are NOT permitted to access this share. Where the lists conflict, the allow list takes precedence. In the event that it is necessary to deny all by default, use the keyword ALL (or the netmask 0.0.0.0/0) and then explicitly specify to the hosts allow parameter those hosts that should be permitted access. Leave this field empty to use default settings.")
            )
    cifs_auxsmbconf = models.TextField(
            max_length=120, 
            verbose_name = _("Auxiliary Parameters"), 
            blank=True,
            help_text = _("These parameters are added to [Share] section of smb.conf")
            )
    
    def __unicode__(self):
        return self.cifs_name
    class Meta:
        verbose_name = _("Windows Share")
    class FreeAdmin:
        icon_model = u"WindowsShareIcon"
        icon_add = u"AddWindowsShareIcon"
        icon_view = u"ViewAllWindowsSharesIcon"
        icon_object = u"WindowsShareIcon"

class AFP_Share(Model):
    afp_name = models.CharField(
            max_length=120, 
            verbose_name = _("Name"),
            help_text = _("The volume name is the name that appears in the Chooser ot the 'connect to server' dialog on Macintoshes to represent the appropriate share. If volumename is unspecified, the last component of pathname is used. No two volumes may have the same name. The volume name cannot contain the ':'  character. The volume name is mangled if it is very long. Mac codepage volume name is limited to 27 characters. UTF8-MAC volume name is limited to 'Volume Name Length' parameter in Services:Apple Share")
            )
    afp_comment = models.CharField(
            max_length=120, 
            verbose_name = _("Share Comment"),
            blank=True
            )
    afp_path = models.ForeignKey(MountPoint, limit_choices_to=mountpoint_limiter, verbose_name = _("Volume Path"))
    afp_sharepw = models.CharField(
            max_length=120, 
            verbose_name = _("Share password"),
            blank=True,
            help_text = _("This option allows you to set a volume password, which can be a maximum of 8 characters long (using ASCII strongly recommended at the time of this writing).")
        )
    afp_sharecharset = models.CharField(
            max_length=120, 
            verbose_name = _("Share Character Set"), 
            blank=True,
            help_text = _("Specifies the share character set. For example UTF8, UTF8-MAC, ISO-8859-15, etc.")
            )
    afp_allow = models.CharField(
            max_length=120, 
            verbose_name = _("Allow List"),
            blank=True,
            help_text = _("This option allows the users and groups that access a share to be specified. Users and groups are specified, delimited by commas. Groups are designated by a @ prefix.")
            )
    afp_deny = models.CharField(
            max_length=120, 
            verbose_name = _("Deny List"),
            blank=True,
            help_text = _("The deny option specifies users and groups who are not allowed access to the share. It follows the same format as the allow option.")
            )
    afp_ro = models.CharField(
            max_length=120, 
            verbose_name = _("Read-only Access"),
            blank=True,
            help_text = _("Allows certain users and groups to have read-only access to a share. This follows the allow option format.")
        )
    afp_rw = models.CharField(
            max_length=120, 
            verbose_name = _("Read-write Access"),
            blank=True,
            help_text = _("Allows certain users and groups to have read/write access to a share. This follows the allow option format. ")
            )
    afp_diskdiscovery = models.BooleanField(
            verbose_name = _("Disk Discovery"),
            help_text = _("Allow other systems to discover this share as a disk for data, as a Time Machine backup volume or not at all.")
            )
    afp_discoverymode = models.CharField(
            max_length=120, 
            choices=choices.DISKDISCOVERY_CHOICES, 
            default='Default', 
            verbose_name = _("Disk discovery mode"),
            help_text = _("Note! Selecting 'Time Machine' on multiple shares will may cause unpredictable behavior in MacOS.  Default mode exports the volume as a data volume for users.")
            )
    afp_dbpath = models.CharField(
            max_length=120, 
            verbose_name = _("Database Path"),
            blank=True,
            help_text = _("Sets the database information to be stored in path. You have to specifiy a writable location, even if the volume is read only.")
            )
    afp_cachecnid = models.BooleanField(
            verbose_name = _("Cache CNID"),
            help_text = _("If set afpd uses the ID information stored in AppleDouble V2 header files to reduce database load. Don't set this option if the volume is modified by non AFP clients (NFS/SMB/local).")
            )
    afp_crlf = models.BooleanField(
            verbose_name = _("Translate CR/LF"),
            help_text = _("Enables crlf translation for TEXT files, automatically converting macintosh line breaks into Unix ones. Use of this option might be dangerous since some older programs store binary data files as type 'TEXT' when saving and switch the filetype in a second step. Afpd will potentially destroy such files when 'erroneously' changing bytes in order to do line break translation.")
            )
    afp_mswindows = models.BooleanField(
            verbose_name = _("Windows File Names"),
            help_text = _("This forces filenames to be restricted to the character set used by Windows. This is not recommended for shares used principally by Mac computers.")
            )
    afp_noadouble = models.BooleanField(
            verbose_name = _("No .AppleDouble"),
            help_text = _("This controls whether the .AppleDouble directory gets created unless absolutely needed. This option should not be used if files are access mostly by Mac computers.  Clicking this option disables their creation.")
            )
    afp_nodev = models.BooleanField(
            verbose_name = _("Zero Device Numbers"),
            help_text = _("Always use 0 for device number, helps when the device number is not constant across a reboot, cluster, ...")
            )
    afp_nofileid = models.BooleanField(
            verbose_name = _("Disable File ID"),
            help_text = _("Don't advertise createfileid, resolveid, deleteid calls.")
            )
    afp_nohex = models.BooleanField(
            verbose_name = _("Disable :hex Names"),
            help_text = _("Disable :hex translations for anything except dot files. This option makes the '/' character illegal.")
            )
    afp_prodos = models.BooleanField(
            verbose_name = _("ProDOS"),
            help_text = _("Provide compatibility with Apple II clients.")
            )
    afp_nostat = models.BooleanField(
            verbose_name = _("No Stat"),
            help_text = _("Don't stat volume path when enumerating volumes list, useful for automounting or volumes created by a preexec script.")
            )
    afp_upriv = models.BooleanField(
            verbose_name = _("AFP3 Unix Privs"),
            help_text = _("Use AFP3 unix privileges.")
            )
    
    def __unicode__(self):
        return unicode(self.afp_name)

    class Meta:
        verbose_name = _("Apple Share")
    class FreeAdmin:
        icon_model = u"AppleShareIcon"
        icon_add = u"AddAppleShareIcon"
        icon_view = u"ViewAllAppleSharesIcon"
        icon_object = u"AppleShareIcon"
    
class NFS_Share(Model):
    nfs_comment = models.CharField(
            max_length=120, 
            verbose_name = _("Comment"),
            blank=True,
            )
    nfs_path = models.ForeignKey(MountPoint, limit_choices_to=mountpoint_limiter, verbose_name = _("Volume Path"))
    nfs_network = models.CharField(
            max_length=120, 
            verbose_name = _("Authorized network or IP addresses"),
            help_text = _("Network that is authorized to access the NFS share or a list of IP addresses.  Specify network numbers of the form 1.2.3.4/xx where xx is the number of bits of netmask or a list of IP addresses 1.2.3.4 1.2.3.5 1.2.3.6."),
            blank=True,
            )
    nfs_alldirs = models.BooleanField(
            verbose_name = _("All Directories"),
            help_text = _("Allow mounting of any subdirectory under this mount point if selected.  Otherwise, only the top level directory can be mounted."),
            )
    nfs_ro = models.BooleanField(
            verbose_name = _("Read Only"),
            help_text = _("Export the share read only.  Writes are not permitted.")
            )
    nfs_quiet = models.BooleanField(
            verbose_name = _("Quiet"),
            help_text = _("Inibit syslog warnings if there are problems with exporting this share.")
            )

    nfs_maproot_user = UserField(
            verbose_name = _("Maproot User"),
            max_length = 120,
            blank = True,
            default = '',
            help_text = _("User to map root to")
            )

    nfs_maproot_group = GroupField(
            verbose_name = _("Maproot Group"),
            max_length = 120,
            blank = True,
            default = '',
            help_text = _("Group to map root to")
            )

    nfs_mapall_user = UserField(
            verbose_name = _("Mapall User"),
            max_length = 120,
            blank = True,
            default = '',
            help_text = _("User to map all users to")
            )
    
    nfs_mapall_group = GroupField(
            verbose_name = _("Mapall Group"),
            max_length = 120,
            blank = True,
            default = '',
            help_text = _("Group to map all users to")
            )

    def __unicode__(self):
        return unicode(self.nfs_path)

    class Meta:
        verbose_name = _("UNIX Share")
    class FreeAdmin:
        icon_model = u"UNIXShareIcon"
        icon_add = u"AddUNIXShareIcon"
        icon_view = u"ViewAllUNIXSharesIcon"
        icon_object = u"UNIXShareIcon"
