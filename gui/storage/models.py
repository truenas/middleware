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

from datetime import time
import os

from django.db import models
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.middleware.notifier import notifier
from freenasUI.common import humanize_size
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
    vol_guid = models.CharField(
            max_length=50,
            blank=True,
            )
    def get_disks(self):
        try:
            if not hasattr(self, '_disks'):
                if self.vol_fstype == 'ZFS':
                    pool = notifier().zpool_parse(self.vol_name)
                    self._disks = pool.get_disks()
                else:
                    prov = notifier().get_label_provider(self.vol_fstype.lower(), self.vol_name)
                    self._disks = notifier().get_disks_from_provider(prov)
            return self._disks
        except Exception, e:
            return []
    def get_datasets(self):
        if self.vol_fstype == 'ZFS':
            return notifier().list_zfs_datasets(path=self.vol_name, recursive=True)
    def get_zvols(self):
        return notifier().list_zfs_vols(self.vol_name)
    def _get_status(self):
        try:
            # Make sure do not compute it twice
            if not hasattr(self, '_status'):
                self._status = notifier().get_volume_status(self.vol_name, self.vol_fstype)
            return self._status
        except Exception, e:
            return _(u"Error")
    status = property(_get_status)
    class Meta:
        verbose_name = _("Volume")
    def has_attachments(self):
        """
        This is mainly used by the VolumeDelete form.
        Responsible for telling the user whether there is a related
        share, asking for confirmation
        """
        services = {}
        for mp in self.mountpoint_set.all():
            for service, ids in mp.has_attachments().items():
                if ids:
                    services[service] = services.get(service, 0) + len(ids)
        return services

    def delete(self, destroy=True, cascade=True):
        """
        Some places reference a path which will not cascade delete
        We need to manually find all paths within this volume mount point
        """
        from services.models import iSCSITargetExtent

        # TODO: This is ugly.
        svcs    = ('cifs', 'afp', 'nfs', 'iscsitarget')
        reloads = (False, False, False,  False)

        if cascade:

            for mp in self.mountpoint_set.all():
                reloads = map(sum, zip(reloads, mp.delete_attachments()))
                mp.delete(do_reload=False)

            zvols = notifier().list_zfs_vols(self.vol_name)
            for zvol in zvols:
                qs = iSCSITargetExtent.objects.filter(iscsi_target_extent_path='zvol/'+zvol,iscsi_target_extent_type='ZVOL')
                if qs.exists():
                    qs.delete()
                    if destroy:
                        retval = notifier().destroy_zfs_vol(name)
                reloads = map(sum, zip(reloads, (False, False, False, True)))

        else:

            for mp in self.mountpoint_set.all():
                attachments = mp.has_attachments()
                reloads = map(sum, zip(reloads, (
                            len(attachments['cifs']),
                            len(attachments['afp']),
                            len(attachments['nfs']),
                            len(attachments['iscsiextent']),
                        )
                        ))

        for (svc, dirty) in zip(svcs, reloads):
            if dirty:
                notifier().stop(svc)

        notifier().detach_volume_swaps(self)

        if destroy:
            notifier().destroy("volume", self)
        else:
            notifier().volume_detach(self.vol_name, self.vol_fstype)

        # The framework would cascade delete all database items
        # referencing this volume.
        super(Volume, self).delete()
        # Refresh the fstab
        notifier().reload("disk")

        for (svc, dirty) in zip(svcs, reloads):
            if dirty:
                notifier().start(svc)

    def __unicode__(self):
        return "%s (%s)" % (self.vol_name, self.vol_fstype)

class Disk(Model):
    disk_name = models.CharField(
            max_length=120,
            verbose_name = _("Name")
            )
    disk_identifier = models.CharField(
            max_length=42,
            verbose_name = _("Identifier")
            )
    disk_serial = models.CharField(
            max_length=30,
            verbose_name = _("Serial"),
            blank=True
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
    disk_enabled = models.BooleanField(
            default=True,
        )
    def get_serial(self):
        return notifier().serial_from_device(
            notifier().identifier_to_device(self.disk_identifier)
            )
    def __init__(self, *args, **kwargs):
        super(Disk, self).__init__(*args, **kwargs)
        self._original_state = dict(self.__dict__)
    def identifier_to_device(self):
        """
        Get the corresponding device name from disk_identifier field
        """
        return notifier().identifier_to_device(self.disk_identifier)
    def save(self, *args, **kwargs):
        if self.id and self._original_state.get("disk_togglesmart", None) != \
                self.__dict__.get("disk_togglesmart"):
            notifier().restart("smartd")
        super(Disk, self).save(args, kwargs)
    def delete(self):
        from freenasUI.services.models import iSCSITargetExtent
        #Delete device extents depending on this Disk
        qs = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk',
                                        iscsi_target_extent_path=str(self.id))
        if qs.exists():
            qs.delete()
        super(Disk, self).delete()
    class Meta:
        verbose_name = _("Disk")
    def __unicode__(self):
        return unicode(self.disk_name)
        #ident = self.identifier_to_device() or _('Unknown')
        #return u"%s" % (ident,)

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
    def is_my_path(self, path):
        import os
        if path == self.mp_path:
            return True
        elif path.find(self.mp_path) >= 0:
            # TODO: This is wrong, need to be fixed by revealing
            # the underlying file system ids.
            rep = path.replace(self.mp_path, self.mp_path+'/')
            if os.path.abspath(rep) == os.path.abspath(path):
                return True
        return False

    def has_attachments(self):
        """
        Return a dict composed by the name of services and ids of shares
        dependent of this MountPoint
        """
        import os
        from sharing.models import CIFS_Share, AFP_Share, NFS_Share
        from services.models import iSCSITargetExtent
        mypath = os.path.abspath(self.mp_path)
        attachments = {
            'cifs': [],
            'afp': [],
            'nfs': [],
            'iscsiextent': [],
        }

        for cifs in CIFS_Share.objects.filter(cifs_path__startswith=mypath):
            if self.is_my_path(cifs.cifs_path):
                attachments['cifs'].append(cifs.id)
        for afp in AFP_Share.objects.filter(afp_path__startswith=mypath):
            if self.is_my_path(afp.afp_path):
                attachments['afp'].append(afp.id)
        for nfs in NFS_Share.objects.filter(nfs_path__startswith=mypath):
            if self.is_my_path(nfs.nfs_path):
                attachments['nfs'].append(nfs.id)
        # TODO: Refactor this into something not this ugly.  The problem
        #       is that iSCSI Extent is not stored in proper relationship
        #       model.
        zvols = notifier().list_zfs_vols(self.mp_volume.vol_name)
        for zvol in zvols:
            qs = iSCSITargetExtent.objects.filter(iscsi_target_extent_path='zvol/'+zvol,iscsi_target_extent_type='ZVOL')
            if qs.exists():
                attachments['iscsiextent'].append(qs[0].id)

        return attachments

    def delete_attachments(self):
        """
        Some places reference a path which will not cascade delete
        We need to manually find all paths within this volume mount point
        """
        from sharing.models import CIFS_Share, AFP_Share, NFS_Share
        from services.models import iSCSITargetExtent

        reload_cifs = False
        reload_afp = False
        reload_nfs = False
        reload_iscsi = False

        # Delete attached paths if they are under our tree.
        # and report if some action needs to be done.
        attachments = self.has_attachments()
        if attachments['cifs']:
            CIFS_Share.objects.filter(id__in=attachments['cifs']).delete()
            reload_cifs = True
        if attachments['afp']:
            AFP_Share.objects.filter(id__in=attachments['afp']).delete()
            reload_afp = True
        if attachments['nfs']:
            NFS_Share.objects.filter(id__in=attachments['nfs']).delete()
            reload_nfs = True
        if attachments['iscsiextent']:
            for target in iSCSITargetExtent.objects.filter(id__in=attachments['iscsiextent']):
                target.delete()
            reload_iscsi = True
        return (reload_cifs, reload_afp, reload_nfs, reload_iscsi)
    def delete(self, do_reload=True):
        reloads = self.delete_attachments()

        if self.mp_volume.vol_fstype == 'ZFS':
            Task.objects.filter(task_filesystem=self.mp_path[5:]).delete()
            Replication.objects.filter(repl_filesystem=self.mp_path[5:]).delete()

        if do_reload:
            svcs = ('cifs', 'afp', 'nfs', 'iscsitarget')
            for (svc, dirty) in zip(svcs, reloads):
                if dirty:
                    notifier().restart(svc)

        super(MountPoint, self).delete()
    def __unicode__(self):
        return self.mp_path
    def _get__vfs(self):
        if not hasattr(self, '__vfs'):
            try:
                self.__vfs = os.statvfs(self.mp_path)
            except:
                self.__vfs = None
        return self.__vfs
    def _get_total_si(self):
        try:
            totalbytes = self._vfs.f_blocks*self._vfs.f_frsize
            return u"%s" % (humanize_size(totalbytes))
        except:
            return _(u"Error getting total space")
    def _get_avail_si(self):
        try:
            availbytes = self._vfs.f_bavail*self._vfs.f_frsize
            return u"%s" % (humanize_size(availbytes))
        except:
            return _(u"Error getting available space")
    def _get_used_bytes(self):
        try:
            return (self._vfs.f_blocks-self._vfs.f_bfree)*self._vfs.f_frsize
        except:
            return 0
    def _get_used_si(self):
        try:
            usedbytes = self._get_used_bytes()
            return u"%s" % (humanize_size(usedbytes))
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
            if not hasattr(self, '_status'):
                self._status = self.mp_volume.status
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
    ssh_remote_port = models.IntegerField(
            default=22,
            verbose_name=_("Remote port"),
            )
    ssh_remote_hostkey = models.CharField(
            max_length=2048,
            verbose_name=_("Remote hostkey"),
            )
    class Meta:
        verbose_name = _(u"Remote Replication Host")
        verbose_name_plural = _(u"Remote Replication Hosts")
    def delete(self):
        rv = super(ReplRemote, self).delete()
        notifier().reload("ssh")
        return rv
    def __unicode__(self):
        return self.ssh_remote_hostname

class Replication(Model):
    repl_filesystem = models.CharField(max_length=150,
            verbose_name = _("Filesystem/Volume"),
            blank = True,
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
    repl_userepl = models.BooleanField(
            default = False,
            verbose_name = _("Recursively replicate and remove stale snapshot on remote side"),
            )
    repl_resetonce = models.BooleanField(
            default = False,
            verbose_name = _("Initialize remote side for once. (May cause data loss on remote side!)"),
            )
    repl_limit = models.IntegerField(
            default = 0,
            verbose_name = _("Limit (kB/s)"),
            help_text = _("Limit the replication speed. Unit in kilobytes/seconds. 0 = unlimited."),
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
        return '%s -> %s' % (self.repl_filesystem, self.repl_remote.ssh_remote_hostname)
    def delete(self):
        try:
            if self.repl_lastsnapshot != "":
                zfsname = self.repl_lastsnapshot.split('@')[0]
                notifier().zfs_inherit_option(zfsname, 'freenas:state', True)
        except:
            pass
        super(Replication, self).delete()

class Task(Model):
    task_filesystem = models.CharField(max_length=150,
            verbose_name = _("Filesystem/Volume"),
            )
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
            choices = choices.TASK_INTERVAL,
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
        return '%s_%s_%d%s' % (self.task_filesystem,
                self.task_repeat_unit, self.task_ret_count, self.task_ret_unit)

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
