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

from datetime import time
from os import statvfs

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.middleware.notifier import notifier
from freenasUI.common import humanize_number_si
from freeadmin.models import Model

class Volume(Model):
    vol_name = models.CharField(
            unique=True,
            max_length=120, 
            verbose_name = _("Name")
            )
    vol_fstype = models.CharField(
            max_length=120, 
            choices=choices.VolumeType_Choices, 
            verbose_name = _("File System Type"), 
            )
    class Meta:
        verbose_name = _("Volume")
    def delete(self):
        notifier().destroy("volume", self.id)
        notifier().restart("collectd")
        # The framework would cascade delete all database items
        # referencing this volume.
        super(Volume, self).delete()
        # Refresh the fstab
        notifier().reload("disk")
    def __unicode__(self):
        return "%s (%s)" % (self.vol_name, self.vol_fstype)

class DiskGroup(Model):
    group_name = models.CharField(
            unique=True,
            max_length=120, 
            verbose_name = _("Name")
            )
    group_type = models.CharField(
            max_length=120, 
            choices=(), 
            verbose_name = _("Type"), 
            )
    group_volume = models.ForeignKey(
            Volume,
            verbose_name = _("Volume"),
            help_text = _("Volume this group belongs to"),
            )
    def __unicode__(self):
        return "%s (%s)" % (self.group_name, self.group_type)

class Disk(Model):
    disk_name = models.CharField(
            unique=True,
            max_length=120, 
            verbose_name = _("Name")
            )
    disk_uuid = models.CharField(
            max_length=36,
            verbose_name = _("UUID")
            )
    disk_disks = models.CharField(
            max_length=120, 
            verbose_name = _("Disks")
            )
    disk_description = models.CharField(
            max_length=120, 
            verbose_name = _("Description"), 
            blank=True
            )
    disk_transfermode = models.CharField(
            max_length=120, 
            choices=choices.TRANSFERMODE_CHOICES, 
            default="Auto", 
            verbose_name = _("Transfer Mode")
            )
    disk_hddstandby = models.CharField(
            max_length=120, 
            choices=choices.HDDSTANDBY_CHOICES, 
            default="Always On", 
            verbose_name = _("HDD Standby")
            )
    disk_advpowermgmt = models.CharField(
            max_length=120, 
            choices=choices.ADVPOWERMGMT_CHOICES, 
            default="Disabled", 
            verbose_name = _("Advanced Power Management")
            )
    disk_acousticlevel = models.CharField(
            max_length=120, 
            choices=choices.ACOUSTICLVL_CHOICES, 
            default="Disabled", 
            verbose_name = _("Acoustic Level")
            )
    disk_togglesmart = models.BooleanField(
            default=True,
            verbose_name = _("Enable S.M.A.R.T."),
            )
    disk_smartoptions = models.CharField(
            max_length=120, 
            verbose_name = _("S.M.A.R.T. extra options"), 
            blank=True
            )
    disk_group = models.ForeignKey(
            DiskGroup,
            verbose_name = _("Group Membership"),
            help_text = _("The disk group containing this disk")
            )
    class Meta:
        verbose_name = _("Disk")
    def __unicode__(self):
        return self.disk_disks + ' (' + self.disk_description + ')'

class MountPoint(Model):
    mp_volume = models.ForeignKey(Volume)
    mp_path = models.CharField(
            unique=True,
            max_length=120,
            verbose_name = _("Mount Point"),
            help_text = _("Path to mount point"),
            )
    mp_options = models.CharField(
            max_length=120,
            verbose_name = _("Mount options"),
            help_text = _("Enter Mount Point options here"),
            null=True,
            )
    mp_ischild = models.BooleanField(
            default=False,
            )
    def __unicode__(self):
        return self.mp_path
    def _get__vfs(self):
        if not hasattr(self, '__vfs'):
            self.__vfs = statvfs(self.mp_path)
        return self.__vfs
    def _get_total_si(self):
        try:
            totalbytes = self._vfs.f_blocks*self._vfs.f_frsize
            return u"%s" % (humanize_number_si(totalbytes))
        except:
            return _(u"Error getting total space")
    def _get_avail_si(self):
        try:
            availbytes = self._vfs.f_bavail*self._vfs.f_frsize
            return u"%s" % (humanize_number_si(availbytes))
        except:
            return _(u"Error getting available space")
    def _get_used_si(self):
        try:
            usedbytes = (self._vfs.f_blocks-self._vfs.f_bfree)*self._vfs.f_frsize
            return u"%s" % (humanize_number_si(usedbytes))
        except:
            return _(u"Error getting used space")
    def _get_used_pct(self):
        try:
            availpct = 100*(self._vfs.f_blocks-self._vfs.f_bavail)/self._vfs.f_blocks
            return u"%d%%" % (availpct)
        except:
            return _(u"Error")
    def _get_status(self):
        try:
            # Make sure do not compute it twice
            if not hasattr(self, '_status'):
                fs = self.mp_volume.vol_fstype
                name = self.mp_volume.vol_name
                group_type = DiskGroup.objects.filter(group_volume__exact=\
                        self.mp_volume).values_list('group_type')
                self._status = notifier().get_volume_status(name, fs, group_type)
            return self._status
        except Exception:
            return _(u"Error")
    _vfs = property(_get__vfs)
    total_si = property(_get_total_si)
    avail_si = property(_get_avail_si)
    used_pct = property(_get_used_pct)
    used_si = property(_get_used_si)
    status = property(_get_status)

# TODO: Refactor replication out from the storage model to its
# own application
class ReplRemote(Model):
    ssh_remote_hostname = models.CharField(
            max_length=120,
            verbose_name=_("Remote hostname"),
            )
    ssh_remote_hostkey = models.CharField(
            max_length=2048,
            verbose_name=_("Remote hostkey"),
            )
    class Meta:
        verbose_name = _(u"Remote Replication Host")
        verbose_name_plural = _(u"Remote Replication Hosts")
    def __unicode__(self):
        return self.ssh_remote_hostname

class Replication(Model):
    repl_mountpoint = models.ForeignKey(MountPoint,
            limit_choices_to = {'mp_volume__vol_fstype__exact' : 'ZFS'},
            verbose_name = _("Mount Point"),
            )
    repl_lastsnapshot = models.CharField(max_length=120,
            blank = True,
            verbose_name = _("Last snapshot sent to remote side (leave blank for full replication)"),
            )
    repl_remote = models.ForeignKey(ReplRemote,
            verbose_name = _("Remote Host"),
            )
    repl_zfs = models.CharField(max_length=120,
            verbose_name = _("Remote ZFS filesystem"),
            )
    class Meta:
        verbose_name = _(u"Replication Task")
        verbose_name_plural = _(u"Replication Tasks")
    class FreeAdmin:
        icon_model = u"ReplIcon"
        icon_add = u"AddReplIcon"
        icon_view = u"ViewAllReplIcon"
        icon_object = u"ReplIcon"
    def __unicode__(self):
        return '%s -> %s' % (self.repl_mountpoint, self.repl_remote.ssh_remote_hostname)

class Task(Model):
    task_mountpoint = models.ForeignKey(MountPoint,
            limit_choices_to = {'mp_volume__vol_fstype__exact' : 'ZFS'},
            verbose_name = _("Mount Point"))
    task_recursive = models.BooleanField(
            default = False,
            verbose_name = _("Recursive"),
            )
    task_ret_count = models.PositiveIntegerField(
            default = 2,
            verbose_name = _("Snapshot lifetime value"),
            )
    task_ret_unit = models.CharField(
            default = 'week',
            max_length = 120,
            choices=choices.RetentionUnit_Choices,
            verbose_name = _("Snapshot lifetime unit"),
            )
    task_begin = models.TimeField(
            default=time(hour=9),
            verbose_name = _("Begin"),
            help_text = _("When in a day should we start making snapshots, e.g. 8:00"),
            )
    task_end = models.TimeField(
            default=time(hour=18),
            verbose_name = _("End"),
            help_text = _("When in a day should we stop making snapshots, e.g. 17:00"),
            )
    task_interval = models.PositiveIntegerField(
            default = 60,
            choices = [(x,"%s minutes" % x) for x in (15, 30, 60, 120, 180, 240)],
            max_length = 120,
            verbose_name = _("Interval"),
            help_text = _("How many minutes passed before a new snapshot is made after the last one."),
            )
    task_repeat_unit = models.CharField(
            default = 'weekly',
            max_length = 120,
            choices=choices.RepeatUnit_Choices,
            verbose_name = _("Occurrence"),
            help_text = _("How the task is repeated"),
            )
    task_byweekday = models.CharField(
            max_length = 120,
            default = "1,2,3,4,5",
            verbose_name = _("Weekday"),
            blank = True,
            )
#    task_bymonth = models.CharField(
#            max_length = 120,
#            default = "1,2,3,4,5,6,7,8,9,a,b,c",
#            verbose_name = _("Month"),
#            blank = True,
#            )
#    task_bymonthday = models.CharField(
#            max_length = 120,
#            verbose_name = _("Day"),
#            blank = True,
#            )
    def __unicode__(self):
        return '%s_%s_%d%s' % (self.task_mountpoint.mp_path[5:], self.task_repeat_unit, self.task_ret_count, self.task_ret_unit)

    class Meta:
        verbose_name = _(u"Periodic Snapshot Task")
        verbose_name_plural = _(u"Periodic Snapshot Tasks")

    class FreeAdmin:
        icon_model = u"SnapIcon"
        icon_add = u"CreatePeriodicSnapIcon"
        icon_view = u"ViewAllPeriodicSnapIcon"
        icon_object = u"SnapIcon"
        extra_js = u"taskrepeat_checkings();"
        menu_children = ["View All Snapshots",]
        composed_fields = (
                            ('Lifetime', ('task_ret_count','task_ret_unit')),
                        )
