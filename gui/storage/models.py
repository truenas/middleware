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
import cPickle
import logging
import os
import re
import uuid
import subprocess

from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import ugettext as __, ugettext_lazy as _

from freenasUI import choices
from freenasUI.middleware import zfs
from freenasUI.middleware.notifier import notifier
from freenasUI.freeadmin.models import Model, UserField

log = logging.getLogger('storage.models')
REPL_RESULTFILE = '/tmp/.repl-result'


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

    @property
    def is_upgraded(self):
        if not self.is_decrypted():
            return True
        try:
            version = notifier().zpool_version(str(self.vol_name))
        except ValueError:
            return True
        if version == '-':
            proc = subprocess.Popen([
                "zpool",
                "get",
                "-H", "-o", "property,value",
                "all",
                str(self.vol_name),
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            data = proc.communicate()[0].strip('\n')
            for line in data.split('\n'):
                if not line.startswith('feature') or '\t' not in line:
                    continue
                prop, value = line.split('\t', 1)
                if value not in ('active', 'enabled'):
                    return False
            return True
        return False

    @property
    def vol_path(self):
        return '/mnt/%s' % self.vol_name

    class Meta:
        verbose_name = _("Volume")

    def get_disks(self):
        try:
            if not hasattr(self, '_disks'):
                n = notifier()
                if self.vol_fstype == 'ZFS':
                    if self.is_decrypted():
                        pool = n.zpool_parse(self.vol_name)
                        self._disks = pool.get_disks()
                    else:
                        self._disks = []
                        for ed in self.encrypteddisk_set.all():
                            if not ed.encrypted_disk:
                                continue
                            if os.path.exists('/dev/{}'.format(ed.encrypted_disk.devname)):
                                self._disks.append(ed.encrypted_disk.devname)
                else:
                    prov = n.get_label_consumer(
                        self.vol_fstype.lower(),
                        self.vol_name)
                    self._disks = n.get_disks_from_provider(prov) \
                        if prov is not None else []
            return self._disks
        except Exception, e:
            log.debug(
                "Exception on retrieving disks for %s: %s",
                self.vol_name,
                e)
            return []

    def get_children(self, hierarchical=True, include_root=True):
        if self.vol_fstype == 'ZFS':
            return zfs.zfs_list(
                path=self.vol_name,
                recursive=True,
                types=["filesystem", "volume"],
                hierarchical=hierarchical,
                include_root=include_root)

    def get_datasets(self, hierarchical=False, include_root=False):
        if self.vol_fstype == 'ZFS':
            return zfs.list_datasets(
                path=self.vol_name,
                recursive=True,
                hierarchical=hierarchical,
                include_root=include_root)

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
        Return a dict composed by the name of services and ids of shares
        dependent of this Volume

        This is mainly used by the VolumeDelete form.
        Responsible for telling the user whether there is a related
        share, asking for confirmation
        """
        from freenasUI.jails.models import Jails, JailsConfiguration
        from freenasUI.sharing.models import (
            CIFS_Share, AFP_Share, NFS_Share_Path
        )
        from freenasUI.services.models import iSCSITargetExtent
        attachments = {
            'cifs': [],
            'afp': [],
            'nfs': [],
            'iscsitarget': [],
            'jails': [],
            'collectd': [],
        }

        for cifs in CIFS_Share.objects.filter(Q(cifs_path=self.vol_path) | Q(cifs_path__startswith=self.vol_path + '/')):
            attachments['cifs'].append(cifs.id)
        for afp in AFP_Share.objects.filter(Q(afp_path=self.vol_path) | Q(afp_path__startswith=self.vol_path + '/')):
            attachments['afp'].append(afp.id)
        for nfsp in NFS_Share_Path.objects.filter(Q(path=self.vol_path) | Q(path__startswith=self.vol_path + '/')):
            if nfsp.share.id not in attachments['nfs']:
                attachments['nfs'].append(nfsp.share.id)
        # TODO: Refactor this into something not this ugly.  The problem
        #       is that iSCSI Extent is not stored in proper relationship
        #       model.
        zvols = notifier().list_zfs_vols(self.vol_name)
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
        if jc and jc.jc_path.startswith(self.vol_path):
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
        reload_collectd = False

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

        return (reload_cifs, reload_afp, reload_nfs, reload_iscsi,
                reload_jails, reload_collectd)

    def _delete(self, destroy=True, cascade=True, systemdataset=None):
        """
        Some places reference a path which will not cascade delete
        We need to manually find all paths within this volume mount point
        """
        from freenasUI.services.models import iSCSITargetExtent

        # If we are using this volume to store collectd data
        # the service needs to be restarted
        if systemdataset and systemdataset.sys_rrd_usedataset:
            reload_collectd = True
        else:
            reload_collectd = False

        # TODO: This is ugly.
        svcs = ('cifs', 'afp', 'nfs', 'iscsitarget', 'jails', 'collectd')
        reloads = (False, False, False, False, False, reload_collectd)

        n = notifier()
        if cascade:

            reloads = map(sum, zip(reloads, self.delete_attachments()))

            zvols = n.list_zfs_vols(self.vol_name)
            for zvol in zvols:
                qs = iSCSITargetExtent.objects.filter(
                    iscsi_target_extent_path='zvol/' + zvol,
                    iscsi_target_extent_type='ZVOL')
                if qs.exists():
                    if destroy:
                        notifier().destroy_zfs_vol(zvol)
                    qs.delete()
                reloads = map(sum, zip(
                    reloads, (False, False, False, True, False,
                              reload_collectd)
                ))

        else:

            attachments = self.has_attachments()
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
            n.volume_detach(self)

        return (svcs, reloads)

    def delete(self, destroy=True, cascade=True):
        from freenasUI.system.models import SystemDataset

        try:
            systemdataset = SystemDataset.objects.filter(
                sys_pool=self.vol_name
            )[0]
        except IndexError:
            systemdataset = None

        with transaction.atomic():
            try:
                svcs, reloads = Volume._delete(
                    self,
                    destroy=destroy,
                    cascade=cascade,
                    systemdataset=systemdataset,
                )
            finally:
                if not os.path.isdir(self.vol_path):
                    do_reload = False

                    if do_reload:
                        reloads = self.delete_attachments()

                    if self.vol_fstype == 'ZFS':
                        Task.objects.filter(task_filesystem=self.vol_name).delete()
                        Replication.objects.filter(
                            repl_filesystem=self.vol_name).delete()

                    if do_reload:
                        svcs = ('cifs', 'afp', 'nfs', 'iscsitarget')
                        for (svc, dirty) in zip(svcs, reloads):
                            if dirty:
                                notifier().restart(svc)

            n = notifier()

            # The framework would cascade delete all database items
            # referencing this volume.
            super(Volume, self).delete()

        # If there's a system dataset on this pool, stop using it.
        if systemdataset:
            systemdataset.sys_pool = ''
            systemdataset.save()
            n.restart('system_datasets')

        # Refresh the fstab
        n.reload("disk")
        # For scrub tasks
        n.restart("cron")

        # Django signal could have been used instead
        # Do it this way to make sure its ran in the time we want
        self.post_delete()

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

    def post_delete(self):
        pass

    def save(self, *args, **kwargs):
        if not self.vol_encryptkey and self.vol_encrypt > 0:
            self.vol_encryptkey = str(uuid.uuid4())
        super(Volume, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.vol_name

    def _get__zplist(self):
        if not hasattr(self, '__zplist'):
            try:
                self.__zplist = zfs.zpool_list().get(self.vol_name)
            except SystemError:
                self.__zplist = None
        return self.__zplist

    def _set__zplist(self, value):
        self.__zplist = value

    def _get__vfs(self):
        if not hasattr(self, '__vfs'):
            try:
                self.__vfs = os.statvfs(self.vol_path)
            except:
                self.__vfs = None
        return self.__vfs

    def _get_avail(self):
        try:
            if self.vol_fstype == 'ZFS':
                return self._zplist['free']
            else:
                return self._vfs.f_bavail * self._vfs.f_frsize
        except:
            if self.is_decrypted():
                return __(u"Error getting available space")
            else:
                return __("Locked")

    def _get_used_bytes(self):
        try:
            if self.vol_fstype == 'ZFS':
                return self._zplist['alloc']
            else:
                return (self._vfs.f_blocks - self._vfs.f_bfree) * \
                    self._vfs.f_frsize
        except:
            return 0

    def _get_used(self):
        try:
            return self._get_used_bytes()
        except:
            if self.is_decrypted():
                return __(u"Error getting used space")
            else:
                return __("Locked")

    def _get_used_pct(self):
        try:
            if self.vol_fstype == 'ZFS':
                return "%d%%" % self._zplist['capacity']
            else:
                availpct = 100 * (self._vfs.f_blocks - self._vfs.f_bavail) / \
                    self._vfs.f_blocks
            return u"%d%%" % availpct
        except:
            return __(u"Error")

    _vfs = property(_get__vfs)
    _zplist = property(_get__zplist, _set__zplist)
    avail = property(_get_avail)
    used_pct = property(_get_used_pct)
    used = property(_get_used)


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
        verbose_name = _("Scrub")
        verbose_name_plural = _("Scrubs")
        ordering = ["scrub_volume__vol_name"]

    def __unicode__(self):
        return self.scrub_volume.vol_name

    def get_human_minute(self):
        if self.scrub_minute == '*':
            return _(u'Every minute')
        elif self.scrub_minute.startswith('*/'):
            return _(u'Every {0} minute(s)').format(self.scrub_minute.split('*/')[1])
        else:
            return self.scrub_minute

    def get_human_hour(self):
        if self.scrub_hour == '*':
            return _(u'Every hour')
        elif self.scrub_hour.startswith('*/'):
            return _(u'Every {0} hour(s)').format(self.scrub_hour.split('*/')[1])
        else:
            return self.scrub_hour

    def get_human_daymonth(self):
        if self.scrub_daymonth == '*':
            return _(u'Everyday')
        elif self.scrub_daymonth.startswith('*/'):
            return _(u'Every {0} days').format(self.scrub_daymonth.split('*/')[1])
        else:
            return self.scrub_daymonth

    def get_human_month(self):
        months = self.scrub_month.split(",")
        if len(months) == 12 or self.scrub_month == '*':
            return _("Every month")
        mchoices = dict(choices.MONTHS_CHOICES)
        labels = []
        for m in months:
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
    disk_identifier = models.CharField(
        max_length=42,
        verbose_name=_("Identifier"),
        editable=False,
        primary_key=True,
    )
    disk_name = models.CharField(
        max_length=120,
        verbose_name=_("Name")
    )
    disk_subsystem = models.CharField(
        default='',
        max_length=10,
        editable=False,
    )
    disk_number = models.IntegerField(
        editable=False,
        default=1,
    )
    disk_serial = models.CharField(
        max_length=30,
        verbose_name=_("Serial"),
        blank=True,
    )
    disk_size = models.CharField(
        max_length=20,
        verbose_name=_('Disk Size'),
        editable=False,
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
        # FIXME
        p1 = subprocess.Popen(
            ["/usr/sbin/diskinfo", self.devname],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        if p1.wait() == 0:
            out = p1.communicate()[0]
            return out.split('\t')[3]
        return 0

    def save(self, *args, **kwargs):
        if self.pk and self._original_state.get("disk_togglesmart", None) != \
                self.__dict__.get("disk_togglesmart"):
            notifier().restart("smartd")
        super(Disk, self).save(*args, **kwargs)

    def delete(self):
        from freenasUI.services.models import iSCSITargetExtent
        # Delete device extents depending on this Disk
        qs = iSCSITargetExtent.objects.filter(
            iscsi_target_extent_type='Disk',
            iscsi_target_extent_path=str(self.pk))
        if qs.exists():
            qs.delete()
        super(Disk, self).delete()

    class Meta:
        verbose_name = _("Disk")
        verbose_name_plural = _("Disks")
        ordering = ["disk_subsystem", "disk_number"]

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
    ssh_cipher = models.CharField(
        max_length=20,
        verbose_name=_('Encryption Cipher'),
        choices=choices.REPL_CIPHER,
        default='standard',
    )

    class Meta:
        verbose_name = _(u"Remote Replication Host")
        verbose_name_plural = _(u"Remote Replication Hosts")

    def delete(self):
        rv = super(ReplRemote, self).delete()
        notifier().reload("ssh")
        return rv

    def __unicode__(self):
        return u"%s:%s" % (self.ssh_remote_hostname, self.ssh_remote_port)


class Replication(Model):
    repl_filesystem = models.CharField(
        max_length=150,
        verbose_name=_("Volume/Dataset"),
        blank=True,
    )
    repl_lastsnapshot = models.CharField(
        max_length=120,
        blank=True,
        editable=False,
        verbose_name=_('Last snapshot sent to remote side'),
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
        verbose_name=_("Recursively replicate child dataset's snapshots"),
    )
    repl_followdelete = models.BooleanField(
        default=False,
        verbose_name=_(
            "Delete stale snapshots on remote system"),
    )
    repl_compression = models.CharField(
        max_length=5,
        choices=choices.Repl_CompressionChoices,
        default="lz4",
        verbose_name=_("Replication Stream Compression"),
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
    repl_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
        help_text=_(
            'Disabling will not stop any replications which are in progress.'
        ),
    )

    class Meta:
        verbose_name = _(u"Replication Task")
        verbose_name_plural = _(u"Replication Tasks")
        ordering = ["repl_filesystem"]

    def __unicode__(self):
        return '%s -> %s:%s' % (
            self.repl_filesystem,
            self.repl_remote.ssh_remote_hostname,
            self.repl_zfs)

    @property
    def repl_lastresult(self):
        if not os.path.exists(REPL_RESULTFILE):
            return 'Waiting'
        with open(REPL_RESULTFILE, 'rb') as f:
            data = f.read()
        try:
            results = cPickle.loads(data)
            return results[self.id]
        except:
            return None

    @property
    def status(self):
        progressfile = '/tmp/.repl_progress_%d' % self.id
        if os.path.exists(progressfile):
            with open(progressfile, 'r') as f:
                pid = int(f.read())
            title = notifier().get_proc_title(pid)
            if title:
                reg = re.search(r'sending (\S+) \((\d+)%', title)
                if reg:
                    return _('Sending %(snapshot)s (%(percent)s%%)') % {
                        'snapshot': reg.groups()[0],
                        'percent': reg.groups()[1],
                    }
                else:
                    return _('Sending')
        if self.repl_lastresult:
            return self.repl_lastresult

    def delete(self):
        try:
            if self.repl_lastsnapshot != "":
                zfsname = self.repl_lastsnapshot.split('@')[0]
                notifier().zfs_dataset_release_snapshots(zfsname, True)
        except:
            pass
        if os.path.exists(REPL_RESULTFILE):
            with open(REPL_RESULTFILE, 'rb') as f:
                data = f.read()
            try:
                results = cPickle.loads(data)
                results.pop(self.id, None)
                with open(REPL_RESULTFILE, 'w') as f:
                    f.write(cPickle.dumps(results))
            except Exception, e:
                log.debug('Failed to remove replication from state file %s', e)
        progressfile = '/tmp/.repl_progress_%d' % self.id
        if os.path.exists(progressfile):
            try:
                os.unlink(progressfile)
            except:
                # Possible race condition?
                pass
        super(Replication, self).delete()


class Task(Model):
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
    task_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
    )

    def __unicode__(self):
        return '%s - every %s - %d%s' % (
            self.task_filesystem,
            self.get_task_interval_display(),
            self.task_ret_count,
            self.task_ret_unit,
        )

    def save(self, *args, **kwargs):
        super(Task, self).save(*args, **kwargs)
        try:
            notifier().restart("cron")
        except:
            pass

    def delete(self, *args, **kwargs):
        super(Task, self).delete(*args, **kwargs)
        try:
            notifier().restart("cron")
        except:
            pass

    class Meta:
        verbose_name = _(u"Periodic Snapshot Task")
        verbose_name_plural = _(u"Periodic Snapshot Tasks")
        ordering = ["task_filesystem"]


class VMWarePlugin(Model):

    hostname = models.CharField(
        verbose_name=_('Hostname'),
        max_length=200,
    )
    username = models.CharField(
        verbose_name=_('Username'),
        max_length=200,
        help_text=_(
            'Username on the above VMware host with enough privileges to '
            'snapshot virtual machines.'
        ),
    )
    password = models.CharField(
        verbose_name=_('Password'),
        max_length=200,
    )
    filesystem = models.CharField(
        verbose_name=_('ZFS Filesystem'),
        max_length=200,
    )
    datastore = models.CharField(
        verbose_name=_('Datastore'),
        max_length=200,
        help_text=_(
            'The datastore on the VMware side that the filesystem corresponds '
            'to.'
        ),
    )

    class Meta:
        verbose_name = _('VMware-Snapshot')
        verbose_name_plural = _('VMware-Snapshots')

    def __unicode__(self):
        return self.hostname

    def set_password(self, passwd):
        self.password = notifier().pwenc_encrypt(passwd)

    def get_password(self):
        return notifier().pwenc_decrypt(self.password)
