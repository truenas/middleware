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
import logging
import os
import uuid

from django.db import models, transaction
from django.utils.translation import ugettext_lazy as _

from freenasUI import choices
from freenasUI.middleware import zfs
from freenasUI.middleware.notifier import notifier
from freenasUI.common import humanize_size
from freenasUI.freeadmin.models import Model, UserField

log = logging.getLogger('storage.models')


class Volume(Model):
    vol_name = models.CharField(
        unique=True,
        max_length=120,
        verbose_name=_("Name")
    )
    vol_fstype = models.CharField(
        max_length=120,
        choices=choices.VolumeType_Choices,
        verbose_name=_("File System Type"),
    )
    vol_guid = models.CharField(
        max_length=50,
        blank=True,
        editable=False,
    )
    vol_encrypt = models.IntegerField(
        choices=choices.VolumeEncrypt_Choices,
        default=0,
        verbose_name=_("Encryption Type"),
    )
    vol_encryptkey = models.CharField(
        max_length=50,
        blank=True,
        editable=False,
    )

    class Meta:
        verbose_name = _("Volume")

    def get_disks(self):
        try:
            if not hasattr(self, '_disks'):
                n = notifier()
                if self.vol_fstype == 'ZFS':
                    pool = n.zpool_parse(self.vol_name)
                    self._disks = pool.get_disks()
                else:
                    prov = n.get_label_consumer(
                        self.vol_fstype.lower(),
                        self.vol_name)
                    self._disks = n.get_disks_from_provider(prov) \
                        if prov else []
            return self._disks
        except Exception, e:
            log.debug(
                "Exception on retrieving disks for %s: %s",
                self.vol_name,
                e)
            return []

    def get_datasets(self, hierarchical=False, include_root=False):
        if self.vol_fstype == 'ZFS':
            return zfs.list_datasets(
                path=self.vol_name,
                recursive=True,
                hierarchical=hierarchical,
                include_root=include_root)

    def get_datasets_with_root(self, hierarchical=False):
        """
        Helper method for template call
        """
        if self.vol_fstype == 'ZFS':
            return zfs.list_datasets(path=self.vol_name,
                recursive=True,
                hierarchical=hierarchical,
                include_root=True)

    def get_zvols(self):
        if self.vol_fstype == 'ZFS':
            return notifier().list_zfs_vols(self.vol_name)

    def _get_status(self):
        try:
            # Make sure do not compute it twice
            if not hasattr(self, '_status'):
                status = notifier().get_volume_status(
                    self.vol_name,
                    self.vol_fstype)
                if status == 'UNKNOWN' and self.vol_encrypt > 0:
                    return _("LOCKED")
                else:
                    self._status = status
            return self._status
        except Exception, e:
            if self.is_decrypted():
                log.debug(
                    "Exception on retrieving status for %s: %s",
                    self.vol_name,
                    e)
                return _(u"Error")
    status = property(_get_status)

    def get_geli_keyfile(self):
        from freenasUI.middleware.notifier import GELI_KEYPATH
        if not os.path.exists(GELI_KEYPATH):
            os.mkdir(GELI_KEYPATH)
        return "%s/%s.key" % (GELI_KEYPATH, self.vol_encryptkey, )

    def is_decrypted(self):
        __is_decrypted = getattr(self, '__is_decrypted', None)
        if __is_decrypted is not None:
            return __is_decrypted

        self.__is_decrypted = True
        # If the status is not UNKNOWN means the pool is already imported
        status = notifier().get_volume_status(self.vol_name, self.vol_fstype)
        if status != 'UNKNOWN':
            return self.__is_decrypted
        if self.vol_encrypt > 0:
            _notifier = notifier()
            for ed in self.encrypteddisk_set.all():
                if not _notifier.geli_is_decrypted(ed.encrypted_provider):
                    self.__is_decrypted = False
                    break
        return self.__is_decrypted

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

    def _delete(self, destroy=True, cascade=True):
        """
        Some places reference a path which will not cascade delete
        We need to manually find all paths within this volume mount point
        """
        from freenasUI.services.models import iSCSITargetExtent

        # TODO: This is ugly.
        svcs = ('cifs', 'afp', 'nfs', 'iscsitarget', 'jails')
        reloads = (False, False, False,  False, False)

        n = notifier()
        if cascade:

            for mp in self.mountpoint_set.all():
                reloads = map(sum, zip(reloads, mp.delete_attachments()))

            zvols = n.list_zfs_vols(self.vol_name)
            for zvol in zvols:
                qs = iSCSITargetExtent.objects.filter(
                    iscsi_target_extent_path='zvol/' + zvol,
                    iscsi_target_extent_type='ZVOL')
                if qs.exists():
                    if destroy:
                        notifier().destroy_zfs_vol(zvol)
                    qs.delete()
                reloads = map(sum, zip(reloads, (False, False, False, True, False)))

        else:

            for mp in self.mountpoint_set.all():
                attachments = mp.has_attachments()
                reloads = map(
                    sum,
                    zip(
                        reloads,
                        [len(attachments[svc]) for svc in svcs]
                    )
                )

        # Delete scheduled snapshots for this volume
        Task.objects.filter(
            models.Q(task_filesystem=self.vol_name)
            |
            models.Q(task_filesystem__startswith="%s/" % self.vol_name)
        ).delete()

        for (svc, dirty) in zip(svcs, reloads):
            if dirty:
                n.stop(svc)

        n.detach_volume_swaps(self)

        # Ghosts volumes, does not exists anymore but is in database
        ghost = False
        try:
            status = n.get_volume_status(self.vol_name, self.vol_fstype)
            ghost = status == 'UNKNOWN'
        except:
            ghost = True

        if ghost:
            pass
        elif destroy:
            n.destroy("volume", self)
        else:
            n.volume_detach(self.vol_name, self.vol_fstype)

        # Detach geli providers
        # TODO: Remove once ZFS bug has been fixed for detach -l
        if self.vol_encrypt > 0:
            for ed in self.encrypteddisk_set.all():
                n.geli_detach(ed.encrypted_provider)

        return (svcs, reloads)

    def delete(self, destroy=True, cascade=True):

        with transaction.commit_on_success():
            try:
                svcs, reloads = Volume._delete(self,
                                               destroy=destroy,
                                               cascade=cascade)
            finally:
                for mp in self.mountpoint_set.all():
                    if not os.path.isdir(mp.mp_path):
                        mp.delete(do_reload=False)

            n = notifier()

            # The framework would cascade delete all database items
            # referencing this volume.
            super(Volume, self).delete()
        # Refresh the fstab
        n.reload("disk")

        if self.vol_encryptkey:
            keyfile = self.get_geli_keyfile()
            if os.path.exists(keyfile):
                try:
                    os.unlink(keyfile)
                except:
                    log.warn("Unable to delete geli key file: %s" % keyfile)

        for (svc, dirty) in zip(svcs, reloads):
            if dirty:
                n.start(svc)

    def save(self, *args, **kwargs):
        if not self.vol_encryptkey and self.vol_encrypt > 0:
            self.vol_encryptkey = str(uuid.uuid4())
        super(Volume, self).save(*args, **kwargs)

    def __unicode__(self):
        return "%s (%s)" % (self.vol_name, self.vol_fstype)


class Scrub(Model):
    scrub_volume = models.OneToOneField(
        Volume,
        verbose_name=_("Volume"),
        limit_choices_to={'vol_fstype': 'ZFS'},
    )
    scrub_threshold = models.PositiveSmallIntegerField(
        verbose_name=_("Threshold days"),
        default=35,
        help_text=_("Determine how many days shall be between scrubs"),
    )
    scrub_description = models.CharField(
        max_length=200,
        verbose_name=_("Description"),
        blank=True,
    )
    scrub_minute = models.CharField(
        max_length=100,
        default="00",
        verbose_name=_("Minute"),
        help_text=_("Values 0-59 allowed."),
    )
    scrub_hour = models.CharField(
        max_length=100,
        default="00",
        verbose_name=_("Hour"),
        help_text=_("Values 0-23 allowed."),
    )
    scrub_daymonth = models.CharField(
        max_length=100,
        default="*",
        verbose_name=_("Day of month"),
        help_text=_("Values 1-31 allowed."),
    )
    scrub_month = models.CharField(
        max_length=100,
        default='*',
        verbose_name=_("Month"),
    )
    scrub_dayweek = models.CharField(
        max_length=100,
        default="7",
        verbose_name=_("Day of week"),
    )
    scrub_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
    )

    class Meta:
        verbose_name = _("ZFS Scrub")
        verbose_name_plural = _("ZFS Scrubs")
        ordering = ["scrub_volume__vol_name"]

    def __unicode__(self):
        return self.scrub_volume.vol_name

    def get_human_minute(self):
        if self.scrub_minute == '*':
            return _(u'Every minute')
        elif self.scrub_minute.startswith('*/'):
            return _(u'Every %s minute(s)') % self.scrub_minute.split('*/')[1]
        else:
            return self.scrub_minute

    def get_human_hour(self):
        if self.scrub_hour == '*':
            return _(u'Every hour')
        elif self.scrub_hour.startswith('*/'):
            return _(u'Every %s hour(s)') % self.scrub_hour.split('*/')[1]
        else:
            return self.scrub_hour

    def get_human_daymonth(self):
        if self.scrub_daymonth == '*':
            return _(u'Everyday')
        elif self.scrub_daymonth.startswith('*/'):
            return _(u'Every %s days') % self.scrub_daymonth.split('*/')[1]
        else:
            return self.scrub_daymonth

    def get_human_month(self):
        months = self.scrub_month.split(",")
        if len(months) == 12 or self.scrub_month == '*':
            return _("Every month")
        mchoices = dict(choices.MONTHS_CHOICES)
        labels = []
        for m in months:
            if m in ('10', '11', '12'):
                m = chr(87 + int(m))
            labels.append(unicode(mchoices[m]))
        return ', '.join(labels)

    def get_human_dayweek(self):
        # TODO:
        # 1. Carve out the days input so that way one can say:
        #    Mon-Fri + Saturday -> Weekdays + Saturday.
        # 2. Get rid of the duplicate code.
        weeks = self.scrub_dayweek.split(',')
        if len(weeks) == 7 or self.scrub_dayweek == '*':
            return _('Everyday')
        if weeks == map(str, xrange(1, 6)):
            return _('Weekdays')
        if weeks == map(str, xrange(6, 8)):
            return _('Weekends')
        wchoices = dict(choices.WEEKDAYS_CHOICES)
        labels = []
        for w in weeks:
            labels.append(unicode(wchoices[str(w)]))
        return ', '.join(labels)

    def delete(self):
        super(Scrub, self).delete()
        try:
            notifier().restart("cron")
        except:
            pass


class Disk(Model):
    disk_name = models.CharField(
        max_length=120,
        verbose_name=_("Name")
    )
    disk_identifier = models.CharField(
        max_length=42,
        verbose_name=_("Identifier"),
        editable=False,
    )
    disk_serial = models.CharField(
        max_length=30,
        verbose_name=_("Serial"),
        blank=True,
    )
    disk_multipath_name = models.CharField(
        max_length=30,
        verbose_name=_("Multipath name"),
        blank=True,
        editable=False,
    )
    disk_multipath_member = models.CharField(
        max_length=30,
        verbose_name=_("Multipath member"),
        blank=True,
        editable=False,
    )
    disk_description = models.CharField(
        max_length=120,
        verbose_name=_("Description"),
        blank=True
    )
    disk_transfermode = models.CharField(
        max_length=120,
        choices=choices.TRANSFERMODE_CHOICES,
        default="Auto",
        verbose_name=_("Transfer Mode")
    )
    disk_hddstandby = models.CharField(
        max_length=120,
        choices=choices.HDDSTANDBY_CHOICES,
        default="Always On",
        verbose_name=_("HDD Standby")
    )
    disk_advpowermgmt = models.CharField(
        max_length=120,
        choices=choices.ADVPOWERMGMT_CHOICES,
        default="Disabled",
        verbose_name=_("Advanced Power Management")
    )
    disk_acousticlevel = models.CharField(
        max_length=120,
        choices=choices.ACOUSTICLVL_CHOICES,
        default="Disabled",
        verbose_name=_("Acoustic Level")
    )
    disk_togglesmart = models.BooleanField(
        default=True,
        verbose_name=_("Enable S.M.A.R.T."),
    )
    disk_smartoptions = models.CharField(
        max_length=120,
        verbose_name=_("S.M.A.R.T. extra options"),
        blank=True
    )
    disk_enabled = models.BooleanField(
        default=True,
        editable=False,
    )

    def get_serial(self):
        n = notifier()
        return n.serial_from_device(
            n.identifier_to_device(self.disk_identifier)
        )

    def __init__(self, *args, **kwargs):
        super(Disk, self).__init__(*args, **kwargs)
        self._original_state = dict(self.__dict__)

    def identifier_to_device(self):
        """
        Get the corresponding device name from disk_identifier field
        """
        return notifier().identifier_to_device(self.disk_identifier)

    @property
    def devname(self):
        if self.disk_multipath_name:
            return "multipath/%s" % self.disk_multipath_name
        else:
            return self.disk_name

    def get_disk_size(self):
        #FIXME
        import subprocess
        p1 = subprocess.Popen(
            ["/usr/sbin/diskinfo", self.devname],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        if p1.wait() == 0:
            out = p1.communicate()[0]
            return out.split('\t')[3]
        return 0

    def save(self, *args, **kwargs):
        if self.id and self._original_state.get("disk_togglesmart", None) != \
                self.__dict__.get("disk_togglesmart"):
            notifier().restart("smartd")
        super(Disk, self).save(*args, **kwargs)

    def delete(self):
        from freenasUI.services.models import iSCSITargetExtent
        #Delete device extents depending on this Disk
        qs = iSCSITargetExtent.objects.filter(
            iscsi_target_extent_type='Disk',
            iscsi_target_extent_path=str(self.id))
        if qs.exists():
            qs.delete()
        super(Disk, self).delete()

    class Meta:
        verbose_name = _("Disk")
        verbose_name_plural = _("Disks")
        ordering = ["disk_name"]

    def __unicode__(self):
        return unicode(self.disk_name)


class EncryptedDisk(Model):
    encrypted_volume = models.ForeignKey(Volume)
    encrypted_disk = models.ForeignKey(
        Disk,
        on_delete=models.SET_NULL,
        null=True,
    )
    encrypted_provider = models.CharField(
        unique=True,
        max_length=120,
        verbose_name=_("Underlying provider"),
    )


class MountPoint(Model):
    mp_volume = models.ForeignKey(Volume)
    mp_path = models.CharField(
        unique=True,
        max_length=120,
        verbose_name=_("Mount Point"),
        help_text=_("Path to mount point"),
    )
    mp_options = models.CharField(
        max_length=120,
        verbose_name=_("Mount options"),
        help_text=_("Enter Mount Point options here"),
        null=True,
    )

    def is_my_path(self, path):
        if path == self.mp_path:
            return True
        try:
            # If the st_dev values match, then it's the same mountpoint.
            return os.stat(self.mp_path).st_dev == os.stat(path).st_dev
        except OSError:
            # Not a real path (most likely). Fallback to a braindead
            # best-effort path check.
            return os.path.commonprefix([self.mp_path, path]) == self.mp_path

    def has_attachments(self):
        """
        Return a dict composed by the name of services and ids of shares
        dependent of this MountPoint
        """
        from freenasUI.jails.models import Jails, JailsConfiguration
        from freenasUI.sharing.models import (
            CIFS_Share, AFP_Share, NFS_Share_Path
        )
        from freenasUI.services.models import iSCSITargetExtent
        mypath = os.path.abspath(self.mp_path)
        attachments = {
            'cifs': [],
            'afp': [],
            'nfs': [],
            'iscsitarget': [],
            'jails': [],
        }

        for cifs in CIFS_Share.objects.filter(cifs_path__startswith=mypath):
            if self.is_my_path(cifs.cifs_path):
                attachments['cifs'].append(cifs.id)
        for afp in AFP_Share.objects.filter(afp_path__startswith=mypath):
            if self.is_my_path(afp.afp_path):
                attachments['afp'].append(afp.id)
        for nfsp in NFS_Share_Path.objects.filter(path__startswith=mypath):
            if (self.is_my_path(nfsp.path)
                    and nfsp.share.id not in attachments['nfs']):
                attachments['nfs'].append(nfsp.share.id)
        # TODO: Refactor this into something not this ugly.  The problem
        #       is that iSCSI Extent is not stored in proper relationship
        #       model.
        zvols = notifier().list_zfs_vols(self.mp_volume.vol_name)
        for zvol in zvols:
            qs = iSCSITargetExtent.objects.filter(
                iscsi_target_extent_path='zvol/' + zvol,
                iscsi_target_extent_type='ZVOL')
            if qs.exists():
                attachments['iscsitarget'].append(qs[0].id)

        try:
            jc = JailsConfiguration.objects.latest("id")
        except:
            jc = None
        if jc and jc.jc_path.startswith(self.mp_path):
            attachments['jails'].extend(
                [j.id for j in Jails.objects.all()]
            )

        return attachments

    def delete_attachments(self):
        """
        Some places reference a path which will not cascade delete
        We need to manually find all paths within this volume mount point
        """
        from freenasUI.sharing.models import CIFS_Share, AFP_Share, NFS_Share
        from freenasUI.services.models import iSCSITargetExtent

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
        if attachments['iscsitarget']:
            for target in iSCSITargetExtent.objects.filter(
                    id__in=attachments['iscsitarget']):
                target.delete()
            reload_iscsi = True
        reload_jails = len(attachments['jails']) > 0

        return (reload_cifs, reload_afp, reload_nfs, reload_iscsi, reload_jails)

    def delete(self, do_reload=True):
        if do_reload:
            reloads = self.delete_attachments()

        if self.mp_volume.vol_fstype == 'ZFS':
            Task.objects.filter(task_filesystem=self.mp_path[5:]).delete()
            Replication.objects.filter(
                repl_filesystem=self.mp_path[5:]).delete()

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
            totalbytes = self._vfs.f_blocks * self._vfs.f_frsize
            return u"%s" % (humanize_size(totalbytes))
        except:
            if self.mp_volume.is_decrypted():
                return _(u"Error getting total space")
            else:
                return _("Locked")

    def _get_avail_si(self):
        try:
            availbytes = self._vfs.f_bavail * self._vfs.f_frsize
            return u"%s" % (humanize_size(availbytes))
        except:
            if self.mp_volume.is_decrypted():
                return _(u"Error getting available space")
            else:
                return _("Locked")

    def _get_used_bytes(self):
        try:
            return (self._vfs.f_blocks - self._vfs.f_bfree) * \
                self._vfs.f_frsize
        except:
            return 0

    def _get_used_si(self):
        try:
            usedbytes = self._get_used_bytes()
            return u"%s" % (humanize_size(usedbytes))
        except:
            if self.mp_volume.is_decrypted():
                return _(u"Error getting used space")
            else:
                return _("Locked")

    def _get_used_pct(self):
        try:
            availpct = 100 * (self._vfs.f_blocks - self._vfs.f_bavail) / \
                self._vfs.f_blocks
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
    ssh_remote_dedicateduser_enabled = models.BooleanField(
        default=False,
        verbose_name=_("Remote Dedicated User Enabled"),
    )
    ssh_remote_dedicateduser = UserField(
        verbose_name=_("Remote Dedicated User"),
        blank=True,
        null=True,
        default='',
    )
    ssh_remote_hostkey = models.CharField(
        max_length=2048,
        verbose_name=_("Remote hostkey"),
    )
    ssh_fast_cipher = models.BooleanField(
        default=False,
        verbose_name=_("High Speed Encryption Ciphers"),
        help_text=_(
            "Enabling this may increase transfer speed on high "
            "speed/low latency local networks.  It uses less secure "
            "encryption algorithms than the defaults, which make it less "
            "desirable on untrusted networks.")
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
    repl_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
        help_text=_(
            "Disabling will stop any new replications being queued. "
            "It will not stop any replications which are queued or in progress."),
    ) 
    repl_filesystem = models.CharField(
        max_length=150,
        verbose_name=_("Volume/Dataset"),
        blank=True,
    )
    repl_lastsnapshot = models.CharField(
        max_length=120,
        blank=True,
        verbose_name=_(
            "Last snapshot sent to remote side (leave blank "
            "for full replication)"),
    )
    repl_remote = models.ForeignKey(
        ReplRemote,
        verbose_name=_("Remote Host"),
    )
    repl_zfs = models.CharField(
        max_length=120,
        verbose_name=_("Remote ZFS Volume/Dataset"),
        help_text=_(
            "This should be the name of the ZFS filesystem on "
            "remote side. eg: Volumename/Datasetname not the mountpoint or "
            "filesystem path"),
    )
    repl_userepl = models.BooleanField(
        default=False,
        verbose_name=_(
            "Recursively replicate and remove stale snapshot "
            "on remote side"),
    )
    repl_resetonce = models.BooleanField(
        default=False,
        verbose_name=_(
            "Initialize remote side for once. (May cause data"
            " loss on remote side!)"),
    )
    repl_limit = models.IntegerField(
        default=0,
        verbose_name=_("Limit (kB/s)"),
        help_text=_(
            "Limit the replication speed. Unit in "
            "kilobytes/seconds. 0 = unlimited."),
    )
    repl_begin = models.TimeField(
        default=time(hour=0),
        verbose_name=_("Begin"),
        help_text=_("Do not start replication before"),
    )
    repl_end = models.TimeField(
        default=time(hour=23, minute=59),
        verbose_name=_("End"),
        help_text=_("Do not start replication after"),
    )

    class Meta:
        verbose_name = _(u"Replication Task")
        verbose_name_plural = _(u"Replication Tasks")
        ordering = ["repl_filesystem"]

    def __unicode__(self):
        return '%s -> %s' % (
            self.repl_filesystem,
            self.repl_remote.ssh_remote_hostname)

    def delete(self):
        try:
            if self.repl_lastsnapshot != "":
                zfsname = self.repl_lastsnapshot.split('@')[0]
                notifier().zfs_inherit_option(zfsname, 'freenas:state', True)
        except:
            pass
        super(Replication, self).delete()


class Task(Model):
    task_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
    ) 
    task_filesystem = models.CharField(
        max_length=150,
        verbose_name=_("Volume/Dataset"),
    )
    task_recursive = models.BooleanField(
        default=False,
        verbose_name=_("Recursive"),
    )
    task_ret_count = models.PositiveIntegerField(
        default=2,
        verbose_name=_("Snapshot lifetime value"),
    )
    task_ret_unit = models.CharField(
        default='week',
        max_length=120,
        choices=choices.RetentionUnit_Choices,
        verbose_name=_("Snapshot lifetime unit"),
    )
    task_begin = models.TimeField(
        default=time(hour=9),
        verbose_name=_("Begin"),
        help_text=_("Do not snapshot before"),
    )
    task_end = models.TimeField(
        default=time(hour=18),
        verbose_name=_("End"),
        help_text=_("Do not snapshot after"),
    )
    task_interval = models.PositiveIntegerField(
        default=60,
        choices=choices.TASK_INTERVAL,
        max_length=120,
        verbose_name=_("Interval"),
        help_text=_(
            "How much time has been passed between two snapshot attempts."),
    )
    task_repeat_unit = models.CharField(
        default='weekly',
        max_length=120,
        choices=choices.RepeatUnit_Choices,
        verbose_name=_("Occurrence"),
        help_text=_("How the task is repeated"),
    )
    task_byweekday = models.CharField(
        max_length=120,
        default="1,2,3,4,5",
        verbose_name=_("Weekday"),
        blank=True,
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
        return '%s - every %s - %d%s' % (
            self.task_filesystem,
            self.get_task_interval_display(),
            self.task_ret_count,
            self.task_ret_unit,
        )

    def save(self, *args, **kwargs):
        super(Task, self).save(args, kwargs)
        try:
            notifier().restart("cron")
        except:
            pass

    def delete(self, *args, **kwargs):
        super(Task, self).delete(args, kwargs)
        try:
            notifier().restart("cron")
        except:
            pass

    class Meta:
        verbose_name = _(u"Periodic Snapshot Task")
        verbose_name_plural = _(u"Periodic Snapshot Tasks")
        ordering = ["task_filesystem"]
