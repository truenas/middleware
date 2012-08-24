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
from collections import OrderedDict
from datetime import datetime, time
from decimal import Decimal
from os import popen, access, stat, mkdir, rmdir
from stat import S_ISDIR
import logging
import os
import re
import tempfile

from django.contrib.auth.models import User, UNUSABLE_PASSWORD
from django.db import transaction
from django.http import QueryDict
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ungettext

from dojango import forms
from dojango.forms import CheckboxSelectMultiple
from freenasUI import choices
from freenasUI.common import humanize_number_si
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common.system import mount, umount
from freenasUI.freeadmin.forms import (CronMultiple, UserField, GroupField,
    WarningSelect)
from freenasUI.middleware import zfs
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.services.models import iSCSITargetExtent, services
from freenasUI.storage import models
from freenasUI.storage.widgets import UnixPermissionField

attrs_dict = {'class': 'required', 'maxHeight': 200}

log = logging.getLogger('storage.forms')

DEDUP_WARNING = _("Enabling dedup may have drastic performance implications,"
    "<br /> as well as impact your ability to access your data.<br /> "
    "Consider using compression instead.")


class Disk(object):

    dev = None
    dtype = None
    number = None
    size = None

    def __init__(self, devname, size, serial=None):
        reg = re.search(r'^(.*?)([0-9]+)', devname)
        if reg:
            self.dtype, number = reg.groups()
        self.number = int(number)
        self.size = size
        self.serial = serial
        self.human_size = humanize_number_si(size)
        self.dev = devname

    def __lt__(self, other):
        if self.human_size == other.human_size:
            if self.dtype == other.dtype:
                return self.number < other.number
            return self.dtype < other.dtype
        return self.size > other.size

    def __repr__(self):
        return u'<Disk: %s>' % str(self)

    def __str__(self):
        extra = ' %s' % (self.serial,) if self.serial else ''
        return u'%s (%s)%s' % (self.dev, humanize_number_si(self.size), extra)

    def __iter__(self):
        yield self.dev
        yield str(self)


def _clean_quota_fields(form, attrs, prefix):

    cdata = form.cleaned_data
    for field in map(lambda x: prefix + x, attrs):
        if field not in cdata:
            cdata[field] = ''

    r = re.compile(r'^(?P<number>[\.0-9]+)(?P<suffix>[KMGT]?)$', re.I)
    msg = _(u"Enter positive number (optionally suffixed by K, M, G, T), "
        "or, 0")

    for attr in attrs:
        formfield = '%s%s' % (prefix, attr)
        match = r.match(cdata[formfield])
        if not match and cdata[formfield] != "0":
            form._errors[formfield] = form.error_class([msg])
            del cdata[formfield]
        elif match:
            number, suffix = match.groups()
            try:
                Decimal(number)
            except:
                form._errors[formfield] = form.error_class([
                    _("%s is not a valid number") % (number, ),
                    ])
                del cdata[formfield]
    return cdata


class VolumeWizardForm(forms.Form):
    volume_name = forms.CharField(
        max_length=30,
        label=_('Volume name'),
        required=False)
    volume_fstype = forms.ChoiceField(
        choices=((x, x) for x in ('UFS', 'ZFS')),
        widget=forms.RadioSelect(attrs=attrs_dict),
        label=_('Filesystem type'))
    volume_disks = forms.MultipleChoiceField(
        choices=(),
        widget=forms.SelectMultiple(attrs=attrs_dict),
        label='Member disks',
        required=False)
    group_type = forms.ChoiceField(
        choices=(),
        widget=forms.RadioSelect(attrs=attrs_dict),
        required=False)
    force4khack = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_('Force 4096 bytes sector size'))
    encryption = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_('Whole disk encryption'))
    dedup = forms.ChoiceField(label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP,
        initial="off",
        )
    ufspathen = forms.BooleanField(
        initial=False,
        label=_('Specify custom path'),
        required=False)
    ufspath = forms.CharField(
        max_length=1024,
        label=_('Path'),
        required=False)

    def __init__(self, *args, **kwargs):
        super(VolumeWizardForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        qs = models.Volume.objects.filter(vol_fstype='ZFS')
        if qs.exists():
            self.fields['volume_add'] = forms.ChoiceField(
                label=_('Volume add'),
                required=False)
            self.fields['volume_add'].choices = [('', '-----')] + \
                                        [(x.vol_name, x.vol_name) for x in qs]
            self.fields['volume_add'].widget.attrs['onChange'] = (
                'wizardcheckings(true);')
        self.fields['volume_fstype'].widget.attrs['onClick'] = (
            'wizardcheckings();')
        self.fields['ufspathen'].widget.attrs['onClick'] = (
            'toggleGeneric("id_ufspathen", ["id_ufspath"], true);')
        if not self.data.get("ufspathen", False):
            self.fields['ufspath'].widget.attrs['disabled'] = 'disabled'
        self.fields['ufspath'].widget.attrs['promptMessage'] = _("Leaving this"
            " blank will give the volume a default path of "
            "/mnt/${VOLUME_NAME}")

        grouptype_choices = (
            ('mirror', 'mirror'),
            ('stripe', 'stripe'),
            )
        fstype = self.data.get("volume_fstype", None)
        if "volume_disks" in self.data:
            disks = self.data.getlist("volume_disks")
        else:
            disks = []
        if fstype == "UFS":
            l = len(disks) - 1
            if l >= 2 and (((l - 1) & l) == 0):
                grouptype_choices += (
                    ('raid3', 'RAID-3'),
                    )
        elif fstype == "ZFS":
            if len(disks) >= 3:
                grouptype_choices += (('raidz', 'RAID-Z'), )
            if len(disks) >= 4:
                grouptype_choices += ( ('raidz2', 'RAID-Z2'), )
            if len(disks) >= 5:
                grouptype_choices += ( ('raidz3', 'RAID-Z3'), )
        self.fields['group_type'].choices = grouptype_choices

    def _populate_disk_choices(self):

        disks = []

        # Grab disk list
        # Root device already ruled out
        for disk, info in notifier().get_disks().items():
            disks.append(Disk(info['devname'], info['capacity'],
                serial=info.get('ident')))

        # Exclude what's already added
        used_disks = []
        for v in models.Volume.objects.all():
            used_disks.extend(v.get_disks())

        qs = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk')
        used_disks.extend([i.get_device()[5:] for i in qs])

        for d in list(disks):
            if d.dev in used_disks:
                disks.remove(d)

        choices = sorted(disks)
        choices = [tuple(d) for d in choices]
        return choices

    def clean_volume_name(self):
        vname = self.cleaned_data['volume_name']
        if vname and not re.search(r'^[a-z][-_.a-z0-9]*$', vname, re.I):
            raise forms.ValidationError(_("The volume name must start with "
                "letters and may include numbers, \"-\", \"_\" and \".\" ."))
        if models.Volume.objects.filter(vol_name=vname).exists():
            raise forms.ValidationError(_("A volume with that name already "
                "exists."))
        return vname

    def clean_group_type(self):
        if 'volume_disks' not in self.cleaned_data or \
                len(self.cleaned_data['volume_disks']) > 1 and \
                self.cleaned_data['group_type'] in (None, ''):
            raise forms.ValidationError(_("This field is required."))
        return self.cleaned_data['group_type']

    def clean_ufspath(self):
        ufspath = self.cleaned_data['ufspath']
        if not ufspath:
            return None
        if not access(ufspath, 0):
            raise forms.ValidationError(_("Path does not exist."))
        st = stat(ufspath)
        if not S_ISDIR(st.st_mode):
            raise forms.ValidationError(_("Path is not a directory."))
        return ufspath

    def clean(self):
        cleaned_data = self.cleaned_data
        volume_name = cleaned_data.get("volume_name", "")
        disks = cleaned_data.get("volume_disks")
        if volume_name and cleaned_data.get("volume_add"):
            self._errors['__all__'] = self.error_class([
                _("You cannot select an existing ZFS volume and specify a new "
                    "volume name"),
                ])
        elif not(volume_name or cleaned_data.get("volume_add")):
            self._errors['__all__'] = self.error_class([
                _("You must specify a new volume name or select an existing "
                    "ZFS volume to append a virtual device"),
                ])
        elif not volume_name:
            volume_name = cleaned_data.get("volume_add")

        if cleaned_data.get("volume_fstype") not in ('ZFS', 'UFS'):
            msg = _(u"You must select a filesystem")
            self._errors["volume_fstype"] = self.error_class([msg])
            cleaned_data.pop("volume_fstype", None)
        if len(disks) == 0 and models.Volume.objects.filter(
                vol_name=volume_name).count() == 0:
            msg = _(u"This field is required")
            self._errors["volume_disks"] = self.error_class([msg])
            del cleaned_data["volume_disks"]
        if (cleaned_data.get("volume_fstype") == 'ZFS' and \
                models.Volume.objects.filter(vol_name=volume_name).exclude(
                    vol_fstype='ZFS').count() > 0
                ) or (
                    cleaned_data.get("volume_fstype") == 'UFS' and \
                    models.Volume.objects.filter(
                        vol_name=volume_name).count() > 0
                ):
            msg = _(u"You already have a volume with same name")
            self._errors["volume_name"] = self.error_class([msg])
            del cleaned_data["volume_name"]

        if cleaned_data.get("volume_fstype", None) == 'ZFS':
            if volume_name in ('log',):
                msg = _(u"\"log\" is a reserved word and thus cannot be used")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)
            elif re.search(r'^c[0-9].*', volume_name) or \
                    re.search(r'^mirror.*', volume_name) or \
                    re.search(r'^spare.*', volume_name) or \
                    re.search(r'^raidz.*', volume_name):
                msg = _(u"The volume name may NOT start with c[0-9], mirror, "
                    "raidz or spare")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)
        elif cleaned_data.get("volume_fstype") == 'UFS' and volume_name:
            if len(volume_name) > 9:
                msg = _(u"UFS volume names cannot be higher than 9 characters")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)
            elif not re.search(r'^[a-z0-9]+$', volume_name, re.I):
                msg = _(u"UFS volume names can only contain alphanumeric "
                    "characters")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)

        return cleaned_data

    def done(self, request):
        # Construct and fill forms into database.
        volume_name = self.cleaned_data.get("volume_name") or \
                            self.cleaned_data.get("volume_add")
        volume_fstype = self.cleaned_data['volume_fstype']
        disk_list = self.cleaned_data['volume_disks']
        force4khack = self.cleaned_data.get("force4khack", False)
        if self.cleaned_data.get("encryption", False):
            volume_encrypt = 1
        else:
            volume_encrypt = 0
        dedup = self.cleaned_data.get("dedup", False)
        ufspath = self.cleaned_data['ufspath']
        mp_options = "rw"
        mp_path = None

        if (len(disk_list) < 2):
            if volume_fstype == 'ZFS':
                group_type = 'stripe'
            else:
                # UFS middleware expects no group_type for single disk volume
                group_type = ''
        else:
            group_type = self.cleaned_data['group_type']

        with transaction.commit_on_success():
            vols = models.Volume.objects.filter(vol_name=volume_name,
                vol_fstype='ZFS')
            if vols.count() == 1:
                volume = vols[0]
                add = True
            else:
                add = False
                volume = models.Volume(vol_name=volume_name,
                    vol_fstype=volume_fstype, vol_encrypt=volume_encrypt)
                volume.save()

                mp_path = ufspath if ufspath else '/mnt/' + volume_name

                if volume_fstype == 'UFS':
                    mp_options = 'rw,nfsv4acls'

                mp = models.MountPoint(mp_volume=volume, mp_path=mp_path,
                    mp_options=mp_options)
                mp.save()
            self.volume = volume

            zpoolfields = re.compile(r'zpool_(.+)')
            grouped = OrderedDict()
            grouped['root'] = {'type': group_type, 'disks': disk_list}
            for i, gtype in request.POST.items():
                if zpoolfields.match(i):
                    if gtype == 'none':
                        continue
                    disk = zpoolfields.search(i).group(1)
                    if gtype in grouped:
                        # if this is a log vdev we need to mirror it for safety
                        if gtype == 'log':
                            grouped[gtype]['type'] = 'log mirror'
                        grouped[gtype]['disks'].append(disk)
                    else:
                        grouped[gtype] = {'type': gtype, 'disks': [disk, ]}

            if len(disk_list) > 0 and add:
                notifier().zfs_volume_attach_group(volume, grouped['root'],
                    force4khack=force4khack)

            if add:
                for grp_type in grouped:
                    if grp_type in ('log', 'cache', 'spare'):
                        notifier().zfs_volume_attach_group(volume,
                            grouped.get(grp_type),
                            force4khack=force4khack)

            else:
                notifier().init("volume", volume, groups=grouped,
                    force4khack=force4khack, path=ufspath)

                if dedup:
                    notifier().zfs_set_option(volume.vol_name, "dedup", dedup)

                if volume.vol_fstype == 'ZFS':
                    models.Scrub.objects.create(scrub_volume=volume)
                    try:
                        notifier().restart("cron")
                    except:
                        pass

        if mp_path in ('/etc', '/var', '/usr'):
            device = '/dev/ufs/' + volume_name
            mp = '/mnt/' + volume_name

            if not access(mp, 0):
                mkdir(mp, 755)

            mount(device, mp)
            popen("/usr/local/bin/rsync -avz '%s/*' '%s/'" % (
                mp_path, mp)
                ).close()
            umount(mp)

            if access(mp, 0):
                rmdir(mp)

        else:

            # This must be outside transaction block to make sure the changes
            # are committed before the call of ix-fstab
            notifier().reload("disk")


class VolumeImportForm(forms.Form):

    volume_name = forms.CharField(max_length=30, label=_('Volume name'))
    volume_disks = forms.ChoiceField(choices=(),
        widget=forms.Select(attrs=attrs_dict),
        label=_('Member disk'))
    volume_fstype = forms.ChoiceField(
        choices=((x, x) for x in ('UFS', 'NTFS', 'MSDOSFS', 'EXT2FS')),
        widget=forms.RadioSelect(attrs=attrs_dict),
        label='File System type')

    def __init__(self, *args, **kwargs):
        super(VolumeImportForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()

    def _populate_disk_choices(self):

        used_disks = []
        for v in models.Volume.objects.all():
            used_disks.extend(v.get_disks())

        qs = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk')
        diskids = [i[0] for i in qs.values_list('iscsi_target_extent_path')]
        used_disks.extend([d.disk_name for d in models.Disk.objects.filter(
            id__in=diskids)])

        n = notifier()
        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        _parts = n.get_partitions()
        for name, part in _parts.items():
            if len([i for i in used_disks \
                    if part['devname'].startswith(i)]) > 0:
                del _parts[name]

        parts = []
        for name, part in _parts.items():
            parts.append(Disk(part['devname'], part['capacity']))

        choices = sorted(parts)
        choices = [tuple(p) for p in choices]
        return choices

    def clean(self):
        cleaned_data = self.cleaned_data
        volume_name = cleaned_data.get("volume_name")
        if models.Volume.objects.filter(vol_name=volume_name).count() > 0:
            msg = _(u"You already have a volume with same name")
            self._errors["volume_name"] = self.error_class([msg])
            del cleaned_data["volume_name"]

        devpath = "/dev/%s" % (cleaned_data.get('volume_disks', []), )
        isvalid = notifier().precheck_partition(devpath,
            cleaned_data.get('volume_fstype', ''))
        if not isvalid:
            msg = _(u"The selected disks were not verified for this import "
                "rules.")
            self._errors["volume_name"] = self.error_class([msg])
            if "volume_name" in cleaned_data:
                del cleaned_data["volume_name"]

        if "volume_name" in cleaned_data:
            dolabel = notifier().label_disk(cleaned_data["volume_name"],
                devpath, cleaned_data['volume_fstype'])
            if not dolabel:
                msg = _(u"An error occurred while labeling the disk.")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)

        return cleaned_data

    def done(self, request):
        # Construct and fill forms into database.
        volume_name = self.cleaned_data['volume_name']
        volume_fstype = self.cleaned_data['volume_fstype']

        volume = models.Volume(vol_name=volume_name, vol_fstype=volume_fstype)
        volume.save()
        self.volume = volume

        mp = models.MountPoint(mp_volume=volume, mp_path='/mnt/' + volume_name,
            mp_options='rw')
        mp.save()

        notifier().start("ix-fstab")
        notifier().mount_volume(volume)
        #notifier().reload("disk")


class VolumeAutoImportForm(forms.Form):

    volume_disks = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs=attrs_dict),
        label=_('Volume'))

    def __init__(self, *args, **kwargs):
        super(VolumeAutoImportForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()

    def _populate_disk_choices(self):

        diskchoices = dict()
        used_disks = []
        for v in models.Volume.objects.all():
            used_disks.extend(v.get_disks())

        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        vols = notifier().detect_volumes()

        for vol in list(vols):
            for vdev in vol['disks']['vdevs']:
                for disk in vdev['disks']:
                    if filter(lambda x: x is not None and \
                                disk['name'].startswith(x),
                            used_disks):
                        vols.remove(vol)
                        break
                else:
                    continue
                break

        for vol in vols:
            if vol.get("id", None):
                devname = "%s [%s, id=%s]" % (
                    vol['label'],
                    vol['type'],
                    vol['id'])
            else:
                devname = "%s [%s]" % (vol['label'], vol['type'])
            diskchoices[vol['label']] = "%s" % (devname,)

        choices = diskchoices.items()
        return choices

    def clean(self):
        cleaned_data = self.cleaned_data
        vols = notifier().detect_volumes()
        for vol in vols:
            if vol['label'] == cleaned_data['volume_disks']:
                cleaned_data['volume'] = vol
                break

        if cleaned_data.get('volume', None) == None:
            self._errors['__all__'] = self.error_class([
                _("You must select a volume."),
                ])

        else:
            if models.Volume.objects.filter(
                    vol_name=cleaned_data['volume']['label']).count() > 0:
                msg = _(u"You already have a volume with same name")
                self._errors["volume_disks"] = self.error_class([msg])
                del cleaned_data["volume_disks"]

            if cleaned_data['volume']['type'] == 'geom':
                if cleaned_data['volume']['group_type'] == 'mirror':
                    dev = "/dev/mirror/%s" % (cleaned_data['volume']['label'])
                elif cleaned_data['volume']['group_type'] == 'stripe':
                    dev = "/dev/stripe/%s" % (cleaned_data['volume']['label'])
                elif cleaned_data['volume']['group_type'] == 'raid3':
                    dev = "/dev/raid3/%s" % (cleaned_data['volume']['label'])
                else:
                    raise NotImplementedError

                isvalid = notifier().precheck_partition(dev, 'UFS')
                if not isvalid:
                    msg = _(u"The selected disks were not verified for this "
                        "import rules.")
                    self._errors["volume_disks"] = self.error_class([msg])

                    if "volume_disks" in cleaned_data:
                        del cleaned_data["volume_disks"]

            elif cleaned_data['volume']['type'] != 'zfs':
                raise NotImplementedError

        return cleaned_data

    def done(self, request):

        vol = self.cleaned_data['volume']
        volume_name = vol['label']
        group_type = vol['group_type']
        if vol['type'] == 'geom':
            volume_fstype = 'UFS'
        elif vol['type'] == 'zfs':
            volume_fstype = 'ZFS'

        with transaction.commit_on_success():
            volume = models.Volume(vol_name=volume_name,
                vol_fstype=volume_fstype)
            volume.save()
            self.volume = volume

            mp = models.MountPoint(mp_volume=volume,
                mp_path='/mnt/' + volume_name,
                mp_options='rw')
            mp.save()

            if vol['type'] != 'zfs':
                notifier().label_disk(volume_name,
                    "%s/%s" % (group_type, volume_name),
                    'UFS')
            else:
                volume.vol_guid = vol['id']
                volume.save()
                models.Scrub.objects.create(scrub_volume=volume)

            if vol['type'] == 'zfs' and not notifier().zfs_import(
                    vol['label'], vol['id']):
                raise MiddlewareError(_('The volume "%s" failed to import, '
                    'for futher details check pool status') % vol['label'])

        notifier().reload("disk")


class DiskFormPartial(ModelForm):
    class Meta:
        model = models.Disk
        exclude = (
            'disk_transfermode',  # This option isn't used anywhere
            )

    def __init__(self, *args, **kwargs):
        super(DiskFormPartial, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self._original_smart_en = self.instance.disk_togglesmart
            self._original_smart_opts = self.instance.disk_smartoptions
            self.fields['disk_name'].widget.attrs['readonly'] = True
            self.fields['disk_name'].widget.attrs['class'] = ('dijitDisabled'
                        ' dijitTextBoxDisabled dijitValidationTextBoxDisabled')
            self.fields['disk_serial'].widget.attrs['readonly'] = True
            self.fields['disk_serial'].widget.attrs['class'] = ('dijitDisabled'
                        ' dijitTextBoxDisabled dijitValidationTextBoxDisabled')

    def clean_disk_name(self):
        return self.instance.disk_name

    def save(self, *args, **kwargs):
        obj = super(DiskFormPartial, self).save(*args, **kwargs)
        if obj.disk_togglesmart != self._original_smart_en or \
            obj.disk_smartoptions != self._original_smart_opts:
            started = notifier().restart("smartd")
            if started is False and \
              services.objects.get(srv_service='smartd').srv_enable:
                raise ServiceFailed("smartd",
                    _("The SMART service failed to restart."))
        return obj


class ZFSDataset_CreateForm(Form):
    dataset_name = forms.CharField(max_length=128,
        label=_('Dataset Name'))
    dataset_compression = forms.ChoiceField(
        choices=choices.ZFS_CompressionChoices,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Compression level'))
    dataset_atime = forms.ChoiceField(
        choices=choices.ZFS_AtimeChoices,
        widget=forms.RadioSelect(attrs=attrs_dict),
        label=_('Enable atime'))
    dataset_refquota = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Quota for this dataset'),
        help_text=_('0=Unlimited; example: 1g'))
    dataset_quota = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Quota for this dataset and all children'),
        help_text=_('0=Unlimited; example: 1g'))
    dataset_refreserv = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Reserved space for this dataset'),
        help_text=_('0=None; example: 1g'))
    dataset_reserv = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Reserved space for this dataset and all children'),
        help_text=_('0=None; example: 1g'))
    dataset_dedup = forms.ChoiceField(label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP_INHERIT,
        widget=WarningSelect(text=DEDUP_WARNING),
        initial="inherit",
        )

    def __init__(self, *args, **kwargs):
        self.fs = kwargs.pop('fs')
        super(ZFSDataset_CreateForm, self).__init__(*args, **kwargs)

    def clean_dataset_name(self):
        name = self.cleaned_data["dataset_name"]
        if not re.search(r'^[a-zA-Z0-9][a-zA-Z0-9_\-:.]*$', name):
            raise forms.ValidationError(_("Dataset names must begin with an "
                "alphanumeric character and may only contain "
                "\"-\", \"_\", \":\" and \".\"."))
        return name

    def clean(self):
        cleaned_data = _clean_quota_fields(self,
            ('refquota', 'quota', 'reserv', 'refreserv'),
            "dataset_")
        full_dataset_name = "%s/%s" % (
            self.fs,
            cleaned_data.get("dataset_name"))
        if len(zfs.list_datasets(path=full_dataset_name)) > 0:
            msg = _(u"You already have a dataset with the same name")
            self._errors["dataset_name"] = self.error_class([msg])
            del cleaned_data["dataset_name"]
        return cleaned_data

    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data


class ZFSDataset_EditForm(Form):
    dataset_compression = forms.ChoiceField(
        choices=choices.ZFS_CompressionChoices,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Compression level'))
    dataset_atime = forms.ChoiceField(
        choices=choices.ZFS_AtimeChoices,
        widget=forms.RadioSelect(attrs=attrs_dict),
        label=_('Enable atime'))
    dataset_refquota = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Quota for this dataset'),
        help_text=_('0=Unlimited; example: 1g'))
    dataset_quota = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Quota for this dataset and all children'),
        help_text=_('0=Unlimited; example: 1g'))
    dataset_refreservation = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Reserved space for this dataset'),
        help_text=_('0=None; example: 1g'))
    dataset_reservation = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Reserved space for this dataset and all children'),
        help_text=_('0=None; example: 1g'))
    dataset_dedup = forms.ChoiceField(label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP_INHERIT,
        widget=WarningSelect(text=DEDUP_WARNING),
        initial="off",
        )

    def __init__(self, *args, **kwargs):
        self._fs = kwargs.pop("fs", None)
        super(ZFSDataset_EditForm, self).__init__(*args, **kwargs)
        data = notifier().zfs_get_options(self._fs)
        self.fields['dataset_compression'].initial = data['compression']
        self.fields['dataset_atime'].initial = data['atime']

        for attr in ('refquota', 'quota', 'reservation', 'refreservation'):
            formfield = 'dataset_%s' % (attr)
            if data[attr] == 'none':
                self.fields[formfield].initial = 0
            else:
                self.fields[formfield].initial = data[attr]

        if data['dedup'] in ('on', 'off', 'verify', 'inherit'):
            self.fields['dataset_dedup'].initial = data['dedup']
        elif data['dedup'] == 'sha256,verify':
            self.fields['dataset_dedup'].initial = 'verify'
        else:
            self.fields['dataset_dedup'].initial = 'off'

    def clean(self):
        return _clean_quota_fields(self,
            ('refquota', 'quota', 'reservation', 'refreservation'),
            "dataset_")

    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data


class ZFSVolume_EditForm(Form):
    volume_compression = forms.ChoiceField(
        choices=choices.ZFS_CompressionChoices,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Compression level'))
    volume_atime = forms.ChoiceField(
        choices=choices.ZFS_AtimeChoices,
        widget=forms.RadioSelect(attrs=attrs_dict),
        label=_('Enable atime'))
    volume_refquota = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Quota for this volume'),
        help_text=_('0=Unlimited; example: 1g'))
    volume_refreservation = forms.CharField(
        max_length=128,
        initial=0,
        label=_('Reserved space for this volume'),
        help_text=_('0=None; example: 1g'))
    volume_dedup = forms.ChoiceField(label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP_INHERIT,
        widget=WarningSelect(text=DEDUP_WARNING),
        )

    def __init__(self, *args, **kwargs):
        self._mp = kwargs.pop("mp", None)
        name = self._mp.mp_path.replace("/mnt/", "")
        super(ZFSVolume_EditForm, self).__init__(*args, **kwargs)
        data = notifier().zfs_get_options(name)
        self.fields['volume_compression'].initial = data['compression']
        self.fields['volume_atime'].initial = data['atime']

        for attr in ('refquota', 'refreservation'):
            formfield = 'volume_%s' % (attr)
            if data[attr] == 'none':
                self.fields[formfield].initial = 0
            else:
                self.fields[formfield].initial = data[attr]

        if data['dedup'] in ('on', 'off', 'verify', 'inherit'):
            self.fields['volume_dedup'].initial = data['dedup']
        elif data['dedup'] == 'sha256,verify':
            self.fields['volume_dedup'].initial = 'verify'
        else:
            self.fields['volume_dedup'].initial = 'off'

    def clean(self):
        return _clean_quota_fields(self,
            ('refquota', 'refreservation'),
            "volume_")

    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data


class ZVol_CreateForm(Form):
    zvol_name = forms.CharField(max_length=128, label=_('ZFS Volume Name'))
    zvol_size = forms.CharField(
        max_length=128,
        label=_('Size for this ZFS Volume'),
        help_text=_('Example: 1g'))
    zvol_compression = forms.ChoiceField(
        choices=choices.ZFS_CompressionChoices,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Compression level'))

    def __init__(self, *args, **kwargs):
        self.vol_name = kwargs.pop('vol_name')
        super(ZVol_CreateForm, self).__init__(*args, **kwargs)

    def clean_dataset_name(self):
        name = self.cleaned_data["zvol_name"]
        if not re.search(r'^[a-zA-Z0-9][a-zA-Z0-9_\-:.]*$', name):
            raise forms.ValidationError(_("ZFS Volume names must begin with "
                "an alphanumeric character and may only contain "
                "(-), (_), (:) and (.)."))
        return name

    def clean(self):
        cleaned_data = self.cleaned_data
        full_zvol_name = "%s/%s" % (
            self.vol_name,
            cleaned_data.get("zvol_name"))
        if len(zfs.list_datasets(path=full_zvol_name)) > 0:
            msg = _(u"You already have a dataset with the same name")
            self._errors["zvol_name"] = self.error_class([msg])
            del cleaned_data["zvol_name"]
        return cleaned_data

    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data


class MountPointAccessForm(Form):
    mp_user = UserField(label=_('Owner (user)'))
    mp_group = GroupField(label=_('Owner (group)'))
    mp_mode = UnixPermissionField(label=_('Mode'))
    mp_acl = forms.ChoiceField(label=_('Type of ACL'), choices=(
        ('unix', 'Unix'),
        ('windows', 'Windows'),
        ), initial='unix', widget=forms.widgets.RadioSelect())
    mp_recursive = forms.BooleanField(initial=False,
                                      required=False,
                                      label=_('Set permission recursively')
                                      )

    def __init__(self, *args, **kwargs):
        super(MountPointAccessForm, self).__init__(*args, **kwargs)

        path = kwargs.get('initial', {}).get('path', None)
        if path:
            if os.path.exists(os.path.join(path, ".windows")):
                self.fields['mp_acl'].initial = 'windows'
            else:
                self.fields['mp_acl'].initial = 'unix'
            user, group = notifier().mp_get_owner(path)
            self.fields['mp_mode'].initial = "%.3o" % (
                notifier().mp_get_permission(path),
                )
            self.fields['mp_user'].initial = user
            self.fields['mp_group'].initial = group

    def commit(self, path='/mnt/'):

        notifier().mp_change_permission(
            path=path,
            user=self.cleaned_data['mp_user'].__str__(),
            group=self.cleaned_data['mp_group'].__str__(),
            mode=self.cleaned_data['mp_mode'].__str__(),
            recursive=self.cleaned_data['mp_recursive'],
            acl=self.cleaned_data['mp_acl'])


class PeriodicSnapForm(ModelForm):

    class Meta:
        model = models.Task
        widgets = {
            'task_byweekday': CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES),
            'task_begin': forms.widgets.TimeInput(attrs={
                'constraints': mark_safe("{timePattern:'HH:mm:ss',}"),
                }),
            'task_end': forms.widgets.TimeInput(attrs={
                'constraints': mark_safe("{timePattern:'HH:mm:ss',}"),
                }),
        }

    def __init__(self, *args, **kwargs):
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            HOUR = re.compile(r'(?P<hour>\d{2}):(?P<min>\d{2}):(?P<sec>\d{2})')
            if "task_begin" in new:
                search = HOUR.search(new['task_begin'])
                new['task_begin'] = time(hour=int(search.group("hour")),
                                           minute=int(search.group("min")),
                                           second=int(search.group("sec")))
            if "task_end" in new:
                search = HOUR.search(new['task_end'])
                new['task_end'] = time(hour=int(search.group("hour")),
                                           minute=int(search.group("min")),
                                           second=int(search.group("sec")))
            args = (new,) + args[1:]
        super(PeriodicSnapForm, self).__init__(*args, **kwargs)
        self.fields['task_filesystem'] = forms.ChoiceField(
                label=self.fields['task_filesystem'].label,
                )
        self.fields['task_filesystem'].choices = (
            notifier().list_zfs_fsvols().items())
        self.fields['task_repeat_unit'].widget = forms.HiddenInput()

    def clean(self):
        cdata = self.cleaned_data
        if cdata['task_repeat_unit'] == 'weekly' and \
                len(cdata['task_byweekday']) == 0:
            self._errors['task_byweekday'] = self.error_class([
                _("At least one day must be chosen"),
                ])
            del cdata['task_byweekday']
        return cdata


class ManualSnapshotForm(Form):
    ms_recursively = forms.BooleanField(
        initial=False,
        required=False,
        label=_('Recursive snapshot'))
    ms_name = forms.CharField(label=_('Snapshot Name'))

    def __init__(self, *args, **kwargs):
        super(ManualSnapshotForm, self).__init__(*args, **kwargs)
        self.fields['ms_name'].initial = datetime.today().strftime(
            'manual-%Y%m%d')

    def clean_ms_name(self):
        regex = re.compile('^[-a-zA-Z0-9_.]+$')
        if regex.match(self.cleaned_data['ms_name'].__str__()) is None:
            raise forms.ValidationError(
                _("Only [-a-zA-Z0-9_.] permitted as snapshot name")
                )
        return self.cleaned_data['ms_name']

    def commit(self, fs):
        notifier().zfs_mksnap(fs, str(self.cleaned_data['ms_name']),
            self.cleaned_data['ms_recursively'])


class CloneSnapshotForm(Form):
    cs_snapshot = forms.CharField(label=_('Snapshot'))
    cs_name = forms.CharField(label=_('Clone Name (must be on same volume)'))

    def __init__(self, *args, **kwargs):
        is_volume = kwargs.pop('is_volume', False)
        super(CloneSnapshotForm, self).__init__(*args, **kwargs)
        self.fields['cs_snapshot'].widget.attrs['readonly'] = True
        self.fields['cs_snapshot'].widget.attrs['class'] = 'dijitDisabled' \
                        ' dijitTextBoxDisabled dijitValidationTextBoxDisabled'
        self.fields['cs_snapshot'].initial = kwargs['initial']['cs_snapshot']
        self.fields['cs_snapshot'].value = kwargs['initial']['cs_snapshot']
        dataset, snapname = kwargs['initial']['cs_snapshot'].split('@')
        if is_volume:
            dataset, zvol = dataset.rsplit('/', 1)
            self.fields['cs_name'].initial = '%s/%s-clone-%s' % (
                dataset,
                zvol,
                snapname)
        else:
            self.fields['cs_name'].initial = '%s/clone-%s' % (
                dataset,
                snapname)

    def clean_cs_snapshot(self):
        return self.fields['cs_snapshot'].initial

    def clean_cs_name(self):
        regex = re.compile('^[-a-zA-Z0-9_./]+$')
        if regex.match(self.cleaned_data['cs_name'].__str__()) is None:
            raise forms.ValidationError(
                _("Only [-a-zA-Z0-9_./] permitted as clone name")
                )
        if '/' in self.fields['cs_snapshot'].initial:
            volname = self.fields['cs_snapshot'].initial.split('/')[0]
        else:
            volname = self.fields['cs_snapshot'].initial.split('@')[0]
        if not self.cleaned_data['cs_name'].startswith('%s/' % (volname)):
            raise forms.ValidationError(
                _("Clone must be within the same volume")
                )
        return self.cleaned_data['cs_name']

    def commit(self):
        snapshot = self.cleaned_data['cs_snapshot'].__str__()
        retval = notifier().zfs_clonesnap(snapshot,
            str(self.cleaned_data['cs_name']))
        return retval


class DiskReplacementForm(forms.Form):

    volume_disks = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs=attrs_dict),
        label=_('Member disk'))

    def __init__(self, *args, **kwargs):
        self.disk = kwargs.pop('disk', None)
        super(DiskReplacementForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        self.fields['volume_disks'].choices.sort(
            key=lambda a: float(
                re.sub(r'^.*?([0-9]+)[^0-9]*([0-9]*).*$', r'\1.\2', a[0])
                ))

    def _populate_disk_choices(self):

        diskchoices = dict()
        used_disks = []
        for v in models.Volume.objects.all():
            used_disks.extend(v.get_disks())
        if self.disk and self.disk in used_disks:
            used_disks.remove(self.disk)

        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        disks = notifier().get_disks()

        for disk in disks:
            if disk in used_disks:
                continue
            devname, capacity = disks[disk]['devname'], disks[disk]['capacity']
            capacity = humanize_number_si(int(capacity))
            if devname == self.disk:
                diskchoices[devname] = "In-place [%s (%s)]" % (
                    devname,
                    capacity)
            else:
                diskchoices[devname] = "%s (%s)" % (devname, capacity)

        choices = diskchoices.items()
        choices.sort(key=lambda a: float(
            re.sub(r'^.*?([0-9]+)[^0-9]*([0-9]*).*$', r'\1.\2', a[0])
            ))
        return choices


class ZFSDiskReplacementForm(DiskReplacementForm):

    def __init__(self, *args, **kwargs):
        super(ZFSDiskReplacementForm, self).__init__(*args, **kwargs)

    def done(self, volume, fromdisk, label):
        devname = self.cleaned_data['volume_disks']
        if devname != fromdisk:
            rv = notifier().zfs_replace_disk(volume, label, devname)
        else:
            rv = notifier().zfs_replace_disk(volume, label, fromdisk)
        if rv == 0:
            return True
        else:
            return False


class UFSDiskReplacementForm(DiskReplacementForm):

    def __init__(self, *args, **kwargs):
        super(UFSDiskReplacementForm, self).__init__(*args, **kwargs)

    def done(self, volume):
        devname = self.cleaned_data['volume_disks']
        rv = notifier().geom_disk_replace(volume, devname)
        if rv == 0:
            return True
        else:
            return False


class ReplicationForm(ModelForm):
    remote_hostname = forms.CharField(label=_("Remote hostname"))
    remote_port = forms.CharField(
        label=_("Remote port"),
        initial=22)
    remote_fast_cipher = forms.BooleanField(
        label=_("Enable High Speed Ciphers"),
        initial=False)
    remote_hostkey = forms.CharField(
        label=_("Remote hostkey"),
        widget=forms.Textarea())

    class Meta:
        model = models.Replication
        exclude = ('repl_lastsnapshot', 'repl_remote', 'repl_limit')
        widgets = {
            'repl_begin': forms.widgets.TimeInput(attrs={
                'constraints': mark_safe("{timePattern:'HH:mm:ss',}"),
                }),
            'repl_end': forms.widgets.TimeInput(attrs={
                'constraints': mark_safe("{timePattern:'HH:mm:ss',}"),
                }),
        }

    def __init__(self, *args, **kwargs):
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            HOUR = re.compile(r'(?P<hour>\d{2}):(?P<min>\d{2}):(?P<sec>\d{2})')
            if "repl_begin" in new:
                search = HOUR.search(new['repl_begin'])
                new['repl_begin'] = time(hour=int(search.group("hour")),
                                           minute=int(search.group("min")),
                                           second=int(search.group("sec")))
            if "repl_end" in new:
                search = HOUR.search(new['repl_end'])
                new['repl_end'] = time(hour=int(search.group("hour")),
                                           minute=int(search.group("min")),
                                           second=int(search.group("sec")))
            args = (new,) + args[1:]
        repl = kwargs.get('instance', None)
        super(ReplicationForm, self).__init__(*args, **kwargs)
        self.fields['repl_filesystem'] = forms.ChoiceField(
                label=self.fields['repl_filesystem'].label,
                )
        fs = list(set([
                (task.task_filesystem, task.task_filesystem)
                for task in models.Task.objects.all()
             ]))
        self.fields['repl_filesystem'].choices = fs
        if repl and repl.id:
            self.fields['remote_hostname'].initial = (
                repl.repl_remote.ssh_remote_hostname)
            self.fields['remote_port'].initial = (
                repl.repl_remote.ssh_remote_port)
            self.fields['remote_fast_cipher'].initial = (
                repl.repl_remote.ssh_fast_cipher)
            self.fields['remote_fast_cipher'].required = (
                False)
            self.fields['remote_fast_cipher'].help_text = _(
                "Enabling this may increase transfer speed on high speed/low latency local networks.  It uses less secure encryption algorithms than the defaults, which makes it less desirable on untrusted networks.")
            self.fields['remote_hostkey'].initial = (
                repl.repl_remote.ssh_remote_hostkey)

    def save(self):
        if self.instance.id == None:
            r = models.ReplRemote()
        else:
            r = self.instance.repl_remote
        r.ssh_remote_hostname = self.cleaned_data.get("remote_hostname")
        r.ssh_remote_hostkey = self.cleaned_data.get("remote_hostkey")
        r.ssh_remote_port = self.cleaned_data.get("remote_port")
        r.ssh_fast_cipher = self.cleaned_data.get("remote_fast_cipher")
        r.save()
        notifier().reload("ssh")
        self.instance.repl_remote = r
        rv = super(ReplicationForm, self).save()
        return rv


class ReplRemoteForm(ModelForm):

    class Meta:
        model = models.ReplRemote

    def save(self):
        rv = super(ReplRemoteForm, self).save()
        notifier().reload("ssh")
        return rv


class VolumeExport(Form):
    mark_new = forms.BooleanField(required=False,
        initial=False,
        label=_("Mark the disks as new (destroy data)"),
        )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        services = kwargs.pop('services', {})
        super(VolumeExport, self).__init__(*args, **kwargs)
        if services.keys():
            self.fields['cascade'] = forms.BooleanField(initial=True,
                    required=False,
                    label=_("Delete all shares related to this volume"))


class Dataset_Destroy(Form):
    def __init__(self, *args, **kwargs):
        self.fs = kwargs.pop('fs')
        self.datasets = kwargs.pop('datasets', [])
        super(Dataset_Destroy, self).__init__(*args, **kwargs)
        snaps = notifier().zfs_snapshot_list(path=self.fs)
        if len(snaps.get(self.fs, [])) > 0:
            label = ungettext(
                "I'm aware this will destroy snapshots within this dataset",
                ("I'm aware this will destroy all child datasets and "
                    "snapshots within this dataset"),
                len(self.datasets)
            )
            self.fields['cascade'] = forms.BooleanField(initial=True,
                label=label)


class ScrubForm(ModelForm):
    class Meta:
        model = models.Scrub
        widgets = {
            'scrub_minute': CronMultiple(
                attrs={'numChoices': 60, 'label': _("minute")},
                ),
            'scrub_hour': CronMultiple(
                attrs={'numChoices': 24, 'label': _("hour")},
                ),
            'scrub_daymonth': CronMultiple(
                attrs={'numChoices': 31,
                    'start': 1,
                    'label': _("day of month")},
                ),
            'scrub_dayweek': forms.CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES),
            'scrub_month': forms.CheckboxSelectMultiple(
                choices=choices.MONTHS_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs:
            ins = kwargs.get('instance')
            if ins.scrub_month == '*':
                ins.scrub_month = "1,2,3,4,5,6,7,8,9,a,b,c"
            else:
                ins.scrub_month = ins.scrub_month.replace("10", "a").replace(
                    "11", "b").replace("12", "c")
            if ins.scrub_dayweek == '*':
                ins.scrub_dayweek = "1,2,3,4,5,6,7"
        super(ScrubForm, self).__init__(*args, **kwargs)

    def clean_scrub_month(self):
        m = eval(self.cleaned_data.get("scrub_month"))
        if len(m) == 12:
            return '*'
        m = ",".join(m)
        m = m.replace("a", "10").replace("b", "11").replace("c", "12")
        return m

    def clean_scrub_dayweek(self):
        w = eval(self.cleaned_data.get("scrub_dayweek"))
        if len(w) == 7:
            return '*'
        w = ",".join(w)
        return w

    def save(self):
        super(ScrubForm, self).save()
        notifier().restart("cron")


class DiskWipeForm(forms.Form):

    method = forms.ChoiceField(
        label=_("Method"),
        choices=(
            ("quick", _("Quick")),
            ("full", _("Full with zeros")),
            ("fullrandom", _("Full with random data")),
        ),
        widget=forms.widgets.RadioSelect(),
        )


class CreatePassphraseForm(forms.Form):

    passphrase = forms.CharField(
        label=_("Passphrase"),
        widget=forms.widgets.PasswordInput(),
        )
    passphrase2 = forms.CharField(
        label=_("Confirm Passphrase"),
        widget=forms.widgets.PasswordInput(),
        )

    def clean_passphrase2(self):
        pass1 = self.cleaned_data.get("passphrase")
        pass2 = self.cleaned_data.get("passphrase2")
        if pass1 != pass2:
            raise forms.ValidationError(
                _("The passphrases do not match")
                )
        return pass2

    def done(self, volume):
        passphrase = self.cleaned_data.get("passphrase")
        if passphrase is not None:
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                f.write(passphrase)
        else:
            passfile = None
        for d in models.EncryptedDisk.objects.filter(encrypted_volume=volume):
            notifier().geli_passphrase(d.encrypted_provider, passfile)
        if passfile is not None:
            os.unlink(passfile)
        volume.vol_encrypt = 2
        volume.save()


class ChangePassphraseForm(forms.Form):

    adminpw = forms.CharField(
        label=_("Admin password"),
        widget=forms.widgets.PasswordInput(),
        )
    passphrase = forms.CharField(
        label=_("New Passphrase"),
        widget=forms.widgets.PasswordInput(),
        )
    passphrase2 = forms.CharField(
        label=_("Confirm New Passphrase"),
        widget=forms.widgets.PasswordInput(),
        )
    remove = forms.BooleanField(
        label=_("Remove passphrase"),
        required=False,
        )

    def __init__(self, *args, **kwargs):
        super(ChangePassphraseForm, self).__init__(*args, **kwargs)
        self.fields['remove'].widget.attrs['onClick'] = (
            'toggleGeneric("id_remove", ["id_passphrase", "id_passphrase2"], false);')
        if self.data.get("remove", False):
            self.fields['passphrase'].widget.attrs['disabled'] = 'disabled'
            self.fields['passphrase2'].widget.attrs['disabled'] = 'disabled'

        user = User.objects.filter(is_superuser=True,
            password=UNUSABLE_PASSWORD)
        if user.exists():
            del self.fields['adminpw']

    def clean_adminpw(self):
        pw = self.cleaned_data.get("adminpw")
        if not User.objects.filter(is_superuser=True)[0].check_password(pw):
            raise forms.ValidationError(
                _("Invalid password")
                )
        return pw

    def clean_passphrase2(self):
        pass1 = self.cleaned_data.get("passphrase")
        pass2 = self.cleaned_data.get("passphrase2")
        if pass1 != pass2:
            raise forms.ValidationError(
                _("The passphrases do not match")
                )
        return pass2

    def clean(self):
        cdata = self.cleaned_data
        if cdata.get("remove"):
            del self._errors['passphrase']
            del self._errors['passphrase2']
        return cdata

    def done(self, volume):
        if self.cleaned_data.get("remove"):
            passphrase = None
        else:
            passphrase = self.cleaned_data.get("passphrase")

        if passphrase is not None:
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                f.write(passphrase)
        else:
            passfile = None
        _notifier = notifier()
        for d in models.EncryptedDisk.objects.filter(encrypted_volume=volume):
            _notifier.geli_passphrase(d.encrypted_provider, passfile)
        if passfile is not None:
            os.unlink(passfile)
            volume.vol_encrypt = 2
        else:
            volume.vol_encrypt = 1
        volume.save()


class UnlockPassphraseForm(forms.Form):

    passphrase = forms.CharField(
        label=_("Passphrase"),
        widget=forms.widgets.PasswordInput(),
        )

    def done(self, volume):
        passphrase = self.cleaned_data.get("passphrase")
        passfile = tempfile.mktemp(dir='/tmp/')
        with open(passfile, 'w') as f:
            f.write(passphrase)
        attached = True
        _notifier = notifier()
        for d in models.EncryptedDisk.objects.filter(encrypted_volume=volume):
            _notifier.geli_attach(d.encrypted_provider, passfile)
        os.unlink(passfile)
        zimport = notifier().zfs_import(volume.vol_name, id=volume.vol_guid)
        if not zimport:
            raise MiddlewareError(_("Volume could not be imported"))


class KeyForm(forms.Form):

    adminpw = forms.CharField(
        label=_("Admin password"),
        widget=forms.widgets.PasswordInput(),
        )

    def __init__(self, *args, **kwargs):
        super(KeyForm, self).__init__(*args, **kwargs)

        user = User.objects.filter(is_superuser=True,
            password=UNUSABLE_PASSWORD)
        if user.exists():
            del self.fields['adminpw']

    def clean_adminpw(self):
        pw = self.cleaned_data.get("adminpw")
        if not User.objects.filter(is_superuser=True)[0].check_password(pw):
            raise forms.ValidationError(
                _("Invalid password")
                )
        return pw
