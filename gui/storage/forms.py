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
from django.contrib.formtools.wizard.views import SessionWizardView
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.forms import FileField
from django.forms.formsets import BaseFormSet, formset_factory
from django.http import HttpResponse, QueryDict
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ungettext

from dojango import forms
from dojango.forms import CheckboxSelectMultiple
from freenasUI import choices
from freenasUI.common import humanize_number_si
from freenasUI.common.forms import ModelForm, Form, mchoicefield
from freenasUI.common.system import mount, umount
from freenasUI.freeadmin.forms import (
    CronMultiple, UserField, GroupField, WarningSelect
)
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware import zfs
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.notifier import notifier, GELI_KEYPATH
from freenasUI.services.exceptions import ServiceFailed
from freenasUI.services.models import iSCSITargetExtent, services
from freenasUI.storage import models
from freenasUI.storage.widgets import UnixPermissionField

attrs_dict = {'class': 'required', 'maxHeight': 200}

log = logging.getLogger('storage.forms')

DEDUP_WARNING = _(
    "Enabling dedup may have drastic performance implications,"
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
    msg = _(u"Enter positive number (optionally suffixed by K, M, G, T), or 0")

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


class VolumeMixin(object):

    def clean_volume_name(self):
        vname = self.cleaned_data['volume_name']
        if vname and not re.search(r'^[a-z][-_.a-z0-9]*$', vname, re.I):
            raise forms.ValidationError(_(
                "The volume name must start with "
                "letters and may include numbers, \"-\", \"_\" and \".\" ."))
        if models.Volume.objects.filter(vol_name=vname).exists():
            raise forms.ValidationError(
                _("A volume with that name already exists."))
        return vname


class VolumeManagerUFSForm(forms.Form, VolumeMixin):
    volume_name = forms.CharField(
        max_length=30,
        label=_('Volume name'),
    )
    volume_disks = forms.MultipleChoiceField(
        choices=(),
        widget=forms.SelectMultiple(attrs=attrs_dict),
        label='Member disks',
        required=False)
    group_type = forms.ChoiceField(
        choices=(),
        widget=forms.RadioSelect(attrs=attrs_dict),
        required=False)
    ufspathen = forms.BooleanField(
        initial=False,
        label=_('Specify custom path'),
        required=False)
    ufspath = forms.CharField(
        max_length=1024,
        label=_('Path'),
        required=False)

    def __init__(self, *args, **kwargs):
        super(VolumeManagerUFSForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        #qs = models.Volume.objects.filter(vol_fstype='ZFS')
        self.fields['ufspathen'].widget.attrs['onClick'] = (
            'toggleGeneric("id_ufspathen", ["id_ufspath"], true);')
        if not self.data.get("ufspathen", False):
            self.fields['ufspath'].widget.attrs['disabled'] = 'disabled'
        self.fields['ufspath'].widget.attrs['promptMessage'] = _(
            "Leaving this blank will give the volume a default path of "
            "/mnt/${VOLUME_NAME}")

        grouptype_choices = (
            ('mirror', 'mirror'),
            ('stripe', 'stripe'),
        )
        if "volume_disks" in self.data:
            disks = self.data.getlist("volume_disks")
        else:
            disks = []
        l = len(disks) - 1
        if l >= 2 and (((l - 1) & l) == 0):
            grouptype_choices += (
                ('raid3', 'RAID-3'),
            )
        self.fields['group_type'].choices = grouptype_choices

    def _populate_disk_choices(self):

        disks = []

        # Grab disk list
        # Root device already ruled out
        for disk, info in notifier().get_disks().items():
            disks.append(Disk(
                info['devname'],
                info['capacity'],
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

    def clean_group_type(self):
        len_disks = len(self.cleaned_data['volume_disks'])
        if 'volume_disks' not in self.cleaned_data or \
                len_disks > 1 and \
                self.cleaned_data['group_type'] in (None, ''):
            raise forms.ValidationError(_("This field is required."))
        if len_disks == 1:
            # UFS middleware expects no group_type for single disk volume
            return ''
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
        disks = cleaned_data.get("volume_disks", [])

        if len(disks) == 0 and models.Volume.objects.filter(
                vol_name=volume_name).count() == 0:
            msg = _(u"This field is required")
            self._errors["volume_disks"] = self.error_class([msg])
            del cleaned_data["volume_disks"]
        if models.Volume.objects.filter(vol_name=volume_name).count():
            msg = _(u"You already have a volume with same name")
            self._errors["volume_name"] = self.error_class([msg])
            del cleaned_data["volume_name"]

        if volume_name:
            if len(volume_name) > 9:
                msg = _(u"UFS volume names cannot be higher than 9 characters")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)
            elif not re.search(r'^[a-z0-9]+$', volume_name, re.I):
                msg = _(
                    u"UFS volume names can only contain alphanumeric "
                    "characters")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)

        return cleaned_data

    def done(self, request):
        # Construct and fill forms into database.
        volume_name = self.cleaned_data.get("volume_name")
        disk_list = self.cleaned_data['volume_disks']
        group_type = self.cleaned_data.get('group_type')
        ufspath = self.cleaned_data['ufspath']

        with transaction.commit_on_success():
            volume = models.Volume(
                vol_name=volume_name,
                vol_fstype='UFS',
            )
            volume.save()

            mp_path = ufspath if ufspath else '/mnt/' + volume_name

            mp = models.MountPoint(
                mp_volume=volume,
                mp_path=mp_path,
                mp_options='rw,nfsv4acls')
            mp.save()
            self.volume = volume

            grouped = OrderedDict()
            grouped['root'] = {'type': group_type, 'disks': disk_list}
            notifier().init(
                "volume",
                volume,
                groups=grouped,
                path=ufspath,
            )

        if mp_path in ('/etc', '/var', '/usr'):
            device = '/dev/ufs/' + volume_name
            mp = '/mnt/' + volume_name

            if not access(mp, 0):
                mkdir(mp, 755)

            mount(device, mp)
            popen("/usr/local/bin/rsync -avzD '%s/*' '%s/'" % (
                mp_path,
                mp,
            )).close()
            umount(mp)

            if access(mp, 0):
                rmdir(mp)

        # This must be outside transaction block to make sure the changes
        # are committed before the call of ix-fstab
        notifier().reload("disk")


class VolumeManagerForm(VolumeMixin, forms.Form):
    volume_name = forms.CharField(
        max_length=30,
        required=False)
    volume_add = forms.CharField(
        max_length=30,
        required=False)
    encryption = forms.BooleanField(
        required=False,
        initial=False,
    )
    encryption_inirand = forms.BooleanField(
        initial=False,
        required=False,
    )
    dedup = forms.ChoiceField(
        choices=choices.ZFS_DEDUP,
        initial="off",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        """
        Compatibility layer required for our API framework
        """
        if 'instance' in kwargs:
            kwargs.pop('instance')
        super(VolumeManagerForm, self).__init__(*args, **kwargs)

    def is_valid(self):
        valid = super(VolumeManagerForm, self).is_valid()
        vdevFormSet = formset_factory(
            VolumeVdevForm,
            formset=VdevFormSet,
        )
        self._formset = vdevFormSet(self.data, prefix='layout')
        self._formset.form = self
        return valid and self._formset.is_valid()

    def clean(self):
        vname = (
            self.cleaned_data.get("volume_name") or
            self.cleaned_data.get("volume_add")
        )
        if not vname:
            self._errors['__all__'] = self.error_class([
                _("You must specify a new volume name or select an existing "
                  "ZFS volume to append a virtual device"),
            ])
        else:
            self.cleaned_data["volume_name"] = vname
        return self.cleaned_data

    def save(self):
        formset = self._formset
        volume_name = self.cleaned_data.get("volume_name")
        init_rand = self.cleaned_data.get("encryption_inirand", False)
        if self.cleaned_data.get("encryption", False):
            volume_encrypt = 1
        else:
            volume_encrypt = 0
        dedup = self.cleaned_data.get("dedup", False)

        with transaction.commit_on_success():
            vols = models.Volume.objects.filter(
                vol_name=volume_name,
                vol_fstype='ZFS')
            if vols.count() > 0:
                volume = vols[0]
                add = True
            else:
                add = False
                volume = models.Volume(
                    vol_name=volume_name,
                    vol_fstype='ZFS',
                    vol_encrypt=volume_encrypt)
                volume.save()

                mp = models.MountPoint(
                    mp_volume=volume,
                    mp_path='/mnt/' + volume_name,
                    mp_options="rw",
                )
                mp.save()
            self.volume = volume

            grouped = OrderedDict()
            #FIXME: Make log as log mirror
            for i, form in enumerate(formset):
                grouped[i] = {
                    'type': form.cleaned_data.get("vdevtype"),
                    'disks': form.cleaned_data.get("disks"),
                }

            if add:
                for gtype, group in grouped.items():
                    notifier().zfs_volume_attach_group(
                        volume,
                        group)

            else:
                notifier().init(
                    "volume",
                    volume,
                    groups=grouped,
                    init_rand=init_rand,
                )

                if dedup:
                    notifier().zfs_set_option(volume.vol_name, "dedup", dedup)

                if volume.vol_fstype == 'ZFS':
                    models.Scrub.objects.create(scrub_volume=volume)

        if volume.vol_encrypt >= 2 and add:
            #FIXME: ask current passphrase to the user
            notifier().geli_passphrase(volume, None)
            volume.vol_encrypt = 1
            volume.save()

        # This must be outside transaction block to make sure the changes
        # are committed before the call of ix-fstab
        notifier().reload("disk")
        # For scrub cronjob
        if volume.vol_fstype == 'ZFS':
            notifier().restart("cron")

        # ModelForm compatibility layer for API framework
        self.instance = volume

        return volume


class VolumeVdevForm(forms.Form):
    vdevtype = forms.CharField(
        max_length=20,
    )
    disks = forms.CharField(
        max_length=200,
        widget=forms.widgets.SelectMultiple(),
    )

    def clean_disks(self):
        vdev = self.cleaned_data.get("vdevtype")
        #TODO: Safe?
        disks = eval(self.cleaned_data.get("disks"))
        errmsg = _("You need at least %d disks")
        if vdev == "mirror" and len(disks) < 2:
            raise forms.ValidationError(errmsg % 2)
        elif vdev == "raidz" and len(disks) < 3:
            raise forms.ValidationError(errmsg % 3)
        elif vdev == "raidz2" and len(disks) < 4:
            raise forms.ValidationError(errmsg % 4)
        elif vdev == "raidz3" and len(disks) < 5:
            raise forms.ValidationError(errmsg % 5)
        return disks

    def clean(self):
        if (
            self.cleaned_data.get("vdevtype") == "log"
            and
            len(self.cleaned_data.get("disks")) > 1
        ):
            self.cleaned_data["vdevtype"] = "log mirror"
        return self.cleaned_data


class VdevFormSet(BaseFormSet):

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form
            # is valid on its own
            return

        if not self.form.cleaned_data.get("volume_add"):
            """
            We need to make sure at least one vdev is a
            data vdev (non-log/cache/spare)
            """
            has_datavdev = False
            for i in range(0, self.total_form_count()):
                form = self.forms[i]
                vdevtype = form.cleaned_data.get('vdevtype')
                if vdevtype in (
                    'mirror', 'stripe', 'raidz', 'raidz2', 'raidz3'
                ):
                    has_datavdev = True
                    break
            if not has_datavdev:
                raise forms.ValidationError(_("You need a data disk group"))


class VolumeImportForm(forms.Form):

    volume_name = forms.CharField(max_length=30, label=_('Volume name'))
    volume_disks = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs=attrs_dict),
        label=_('Member disk'),
    )
    volume_fstype = forms.ChoiceField(
        choices=((x, x) for x in ('UFS', 'NTFS', 'MSDOSFS', 'EXT2FS')),
        widget=forms.RadioSelect(attrs=attrs_dict),
        label='File System type',
    )

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
            for i in used_disks:
                if re.search(r'^%s([ps]|$)' % i, part['devname']) is not None:
                    del _parts[name]
                    continue

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
        isvalid = notifier().precheck_partition(
            devpath,
            cleaned_data.get('volume_fstype', ''))
        if not isvalid:
            msg = _(
                u"The selected disks were not verified for this import rules.")
            self._errors["volume_name"] = self.error_class([msg])
            if "volume_name" in cleaned_data:
                del cleaned_data["volume_name"]

        if "volume_name" in cleaned_data:
            dolabel = notifier().label_disk(
                cleaned_data["volume_name"],
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

        mp = models.MountPoint(
            mp_volume=volume,
            mp_path='/mnt/' + volume_name,
            mp_options='rw')
        mp.save()

        notifier().start("ix-fstab")
        notifier().mount_volume(volume)
        #notifier().reload("disk")


def show_descrypt_condition(wizard):
    cleaned_data = wizard.get_cleaned_data_for_step('0') or {}
    if cleaned_data.get("step") == "decrypt":
        return True
    else:
        return False


class AutoImportWizard(SessionWizardView):
    file_storage = FileSystemStorage(location='/var/tmp/firmware')

    def get_template_names(self):
        return [
            'storage/autoimport_wizard_%s.html' % self.get_step_index(),
            'storage/autoimport_wizard.html',
        ]

    def process_step(self, form):
        proc = super(AutoImportWizard, self).process_step(form)
        """
        We execute the form done method if there is one, for each step
        """
        if hasattr(form, 'done'):
            retval = form.done(
                request=self.request,
                form_list=self.form_list,
                wizard=self)
            if self.get_step_index() == self.steps.count - 1:
                self.retval = retval
        return proc

    def render_to_response(self, context, **kwargs):
        response = super(AutoImportWizard, self).render_to_response(
            context,
            **kwargs
        )
        # This is required for the workaround dojo.io.frame for file upload
        if not self.request.is_ajax():
            return HttpResponse(
                "<html><body><textarea>"
                + response.rendered_content +
                "</textarea></boby></html>")
        return response

    def done(self, form_list, **kwargs):

        cdata = self.get_cleaned_data_for_step('1') or {}
        enc_disks = cdata.get("disks", [])
        key = cdata.get("key")
        passphrase = cdata.get("passphrase")
        passfile = None
        if key and passphrase:
            encrypt = 2
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                os.chmod(passfile, 600)
                f.write(passphrase)
        elif key:
            encrypt = 1
        else:
            encrypt = 0

        cdata = self.get_cleaned_data_for_step('2') or {}
        vol = cdata['volume']
        volume_name = vol['label']
        group_type = vol['group_type']
        if vol['type'] == 'geom':
            volume_fstype = 'UFS'
        elif vol['type'] == 'zfs':
            volume_fstype = 'ZFS'

        try:
            with transaction.commit_on_success():
                volume = models.Volume(
                    vol_name=volume_name,
                    vol_fstype=volume_fstype,
                    vol_encrypt=encrypt)
                volume.save()
                if encrypt > 0:
                    if not os.path.exists(GELI_KEYPATH):
                        os.mkdir(GELI_KEYPATH)
                    key.seek(0)
                    keydata = key.read()
                    with open(volume.get_geli_keyfile(), 'wb') as f:
                        f.write(keydata)
                self.volume = volume

                mp = models.MountPoint(
                    mp_volume=volume,
                    mp_path='/mnt/' + volume_name,
                    mp_options='rw')
                mp.save()

                if vol['type'] != 'zfs':
                    notifier().label_disk(
                        volume_name,
                        "%s/%s" % (group_type, volume_name),
                        'UFS')
                else:
                    volume.vol_guid = vol['id']
                    volume.save()
                    models.Scrub.objects.create(scrub_volume=volume)

                if vol['type'] == 'zfs' and not notifier().zfs_import(
                        vol['label'], vol['id']):
                    raise MiddlewareError(_(
                        'The volume "%s" failed to import, '
                        'for futher details check pool status') % vol['label'])
                for disk in enc_disks:
                    notifier().geli_setkey(
                        "/dev/%s" % disk,
                        volume.get_geli_keyfile(),
                        passphrase=passfile
                    )
                    if disk.startswith("gptid"):
                        diskname = notifier().identifier_to_device(
                            "{uuid}%s" % disk.replace("gptid/", "")
                        )
                    else:
                        diskname = disk
                    ed = models.EncryptedDisk()
                    ed.encrypted_volume = volume
                    ed.encrypted_disk = models.Disk.objects.filter(
                        disk_name=diskname,
                        disk_enabled=True
                    )[0]
                    ed.encrypted_provider = disk
                    ed.save()
        except:
            if passfile:
                os.unlink(passfile)
            raise

        notifier().reload("disk")

        return JsonResp(self.request, message=unicode(_("Volume imported")))


class AutoImportChoiceForm(forms.Form):
    step = forms.ChoiceField(
        choices=(
            ('import', _("No: Skip to import")),
            ('decrypt', _("Yes: Decrypt disks")),
        ),
        label=_("Encrypted ZFS volume?"),
        widget=forms.RadioSelect(),
        initial="import",
    )

    def done(self, *args, **kwargs):
        # Detach all unused geli providers before proceeding
        # This makes sure do not import pools without proper key
        _notifier = notifier()
        for dev, name in notifier().geli_get_all_providers():
            _notifier.geli_detach(dev)


class AutoImportDecryptForm(forms.Form):
    disks = forms.MultipleChoiceField(
        choices=(),
    )
    key = FileField(
        label=_("Encryption Key"),
    )
    passphrase = forms.CharField(
        label=_("Passphrase"),
        required=False,
        widget=forms.widgets.PasswordInput(),
    )

    def __init__(self, *args, **kwargs):
        super(AutoImportDecryptForm, self).__init__(*args, **kwargs)
        self.fields['disks'].choices = self._populate_disk_choices()

    def _populate_disk_choices(self):
        return notifier().geli_get_all_providers()

    def clean(self):
        key = self.cleaned_data.get("key")
        if not key:
            return self.cleaned_data

        disks = self.cleaned_data.get("disks")
        if not disks:
            return self.cleaned_data

        passphrase = self.cleaned_data.get("passphrase")
        if passphrase:
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                os.chmod(passfile, 600)
                f.write(passphrase)
            passphrase = passfile

        keyfile = tempfile.mktemp(dir='/var/tmp/firmware')
        with open(keyfile, 'wb') as f:
            os.chmod(keyfile, 600)
            f.write(key.read())

        _notifier = notifier()
        failed = []
        for disk in disks:
            if not _notifier.geli_attach_single(
                disk,
                keyfile,
                passphrase=passphrase
            ):
                failed.append(disk)
        if failed:
            self._errors['__all__'] = self.error_class([
                _("The following disks failed to attach: %s") % (
                    ', '.join(failed),
                )
            ])
        os.unlink(keyfile)
        if passphrase:
            os.unlink(passphrase)
        return self.cleaned_data


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
                    if filter(lambda x: x is not None and re.search(
                        r'^%s([ps]|$)' % disk['name'],
                        x
                    ), used_disks):
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
            diskchoices["%s|%s" % (vol['label'], vol.get('id', ''))] = devname

        choices = diskchoices.items()
        return choices

    def clean(self):
        cleaned_data = self.cleaned_data
        vols = notifier().detect_volumes()
        volume_name, zid = cleaned_data.get('volume_disks', '|').split('|', 1)
        for vol in vols:
            if vol['label'] == volume_name:
                if (zid and zid == vol['id']) or not zid:
                    cleaned_data['volume'] = vol
                    break

        if cleaned_data.get('volume', None) is None:
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
                    msg = _(
                        u"The selected disks were not verified for this "
                        "import rules.")
                    self._errors["volume_disks"] = self.error_class([msg])

                    if "volume_disks" in cleaned_data:
                        del cleaned_data["volume_disks"]

            elif cleaned_data['volume']['type'] != 'zfs':
                raise NotImplementedError

        return cleaned_data


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
            self.fields['disk_name'].widget.attrs['class'] = (
                'dijitDisabled dijitTextBoxDisabled '
                'dijitValidationTextBoxDisabled')
            self.fields['disk_serial'].widget.attrs['readonly'] = True
            self.fields['disk_serial'].widget.attrs['class'] = (
                'dijitDisabled dijitTextBoxDisabled '
                'dijitValidationTextBoxDisabled')

    def clean_disk_name(self):
        return self.instance.disk_name

    def save(self, *args, **kwargs):
        obj = super(DiskFormPartial, self).save(*args, **kwargs)
        # Commit ataidle changes, if any
        if (
            obj.disk_hddstandby != obj._original_state['disk_hddstandby']
            or
            obj.disk_advpowermgmt != obj._original_state['disk_advpowermgmt']
            or
            obj.disk_acousticlevel != obj._original_state['disk_acousticlevel']
        ):
            notifier().start_ataidle(obj.disk_name)

        if (
            obj.disk_togglesmart != self._original_smart_en or
            obj.disk_smartoptions != self._original_smart_opts
        ):
            started = notifier().restart("smartd")
            if (
                started is False
                and
                services.objects.get(srv_service='smartd').srv_enable
            ):
                raise ServiceFailed(
                    "smartd",
                    _("The SMART service failed to restart.")
                )
        return obj


class DiskEditBulkForm(Form):

    ids = forms.CharField(
        widget=forms.widgets.HiddenInput(),
    )
    disk_hddstandby = forms.ChoiceField(
        choices=(('', '-----'),) + choices.HDDSTANDBY_CHOICES,
        required=False,
        initial="Always On",
        label=_("HDD Standby")
    )
    disk_advpowermgmt = forms.ChoiceField(
        required=False,
        choices=(('', '-----'),) + choices.ADVPOWERMGMT_CHOICES,
        label=_("Advanced Power Management")
    )
    disk_acousticlevel = forms.ChoiceField(
        required=False,
        choices=(('', '-----'),) + choices.ACOUSTICLVL_CHOICES,
        label=_("Acoustic Level")
    )
    disk_togglesmart = forms.BooleanField(
        initial=True,
        label=_("Enable S.M.A.R.T."),
        required=False,
    )
    disk_smartoptions = forms.CharField(
        max_length=120,
        label=_("S.M.A.R.T. extra options"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self._disks = kwargs.pop('disks')
        super(DiskEditBulkForm, self).__init__(*args, **kwargs)
        self.fields['ids'].initial = ','.join([str(d.id) for d in self._disks])

        """
        Make sure all the disks have a same option for each field
        If they are not default to empty.
        """
        initials = {}
        for disk in self._disks:

            for opt in (
                'disk_hddstandby',
                'disk_advpowermgmt',
                'disk_acousticlevel',
                'disk_smartoptions',
            ):
                if opt not in initials:
                    initials[opt] = getattr(disk, opt)
                elif initials[opt] != getattr(disk, opt):
                    initials[opt] = ''

            if 'disk_togglesmart' not in initials:
                initials['disk_togglesmart'] = disk.disk_togglesmart
            elif initials['disk_togglesmart'] != disk.disk_togglesmart:
                initials['disk_togglesmart'] = True

        for key, val in initials.items():
            self.fields[key].initial = val

    def save(self):

        with transaction.commit_on_success():
            for disk in self._disks:

                for opt in (
                    'disk_hddstandby',
                    'disk_advpowermgmt',
                    'disk_acousticlevel',
                ):
                    if self.cleaned_data.get(opt):
                        setattr(disk, opt, self.cleaned_data.get(opt))

                disk.disk_togglesmart = self.cleaned_data.get(
                    "disk_togglesmart")
                # This is not a choice field, an empty value should reset all
                disk.disk_smartoptions = self.cleaned_data.get(
                    "disk_smartoptions")
                disk.save()
        return self._disks


class ZFSDataset_CreateForm(Form):
    dataset_name = forms.CharField(
        max_length=128,
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
    dataset_dedup = forms.ChoiceField(
        label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP_INHERIT,
        widget=WarningSelect(text=DEDUP_WARNING),
        initial="inherit",
    )
    dataset_recordsize = forms.CharField(
        label=_('Record Size'),
        initial="",
        required=False,
        help_text=_(
            "Specifies a suggested block size for files in the file system. "
            "This property is designed solely for use with database workloads "
            "that access files in fixed-size records.  ZFS automatically tunes"
            " block sizes according to internal algorithms optimized for "
            "typical access patterns."
        )
    )

    advanced_fields = (
        'dataset_refquota',
        'dataset_quota',
        'dataset_refreserv',
        'dataset_reserv',
        'dataset_recordsize'
    )

    def __init__(self, *args, **kwargs):
        self.fs = kwargs.pop('fs')
        super(ZFSDataset_CreateForm, self).__init__(*args, **kwargs)

    def clean_dataset_name(self):
        name = self.cleaned_data["dataset_name"]
        if not re.search(r'^[a-zA-Z0-9][a-zA-Z0-9_\-:.]*$', name):
            raise forms.ValidationError(_(
                "Dataset names must begin with an "
                "alphanumeric character and may only contain "
                "\"-\", \"_\", \":\" and \".\"."))
        return name

    def clean_dataset_recordsize(self):
        rs = self.cleaned_data.get("dataset_recordsize")
        if not rs:
            return rs
        if not re.search(r'^[0-9]+K?', rs, re.I):
            raise forms.ValidationError(_("This is not a valid record size"))
        if rs[-1].lower() == 'k':
            rs = int(rs[:-1]) * 1024
        else:
            rs = int(rs)
        poftwo = pow(rs, 0.5)
        if (rs < 512 or rs > 131072) or poftwo != int(poftwo):
            raise forms.ValidationError(_(
                "The size specified must be a power of two greater than or "
                "equal to 512 and less than or equal to 128 Kbytes."
            ))
        return rs

    def clean(self):
        cleaned_data = _clean_quota_fields(
            self,
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
    dataset_dedup = forms.ChoiceField(
        label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP_INHERIT,
        widget=WarningSelect(text=DEDUP_WARNING),
        initial="off",
    )

    advanced_fields = (
        'dataset_refquota',
        'dataset_quota',
        'dataset_refreservation',
        'dataset_reservation',
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
        return _clean_quota_fields(
            self,
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
    volume_dedup = forms.ChoiceField(
        label=_('ZFS Deduplication'),
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
        return _clean_quota_fields(
            self,
            ('refquota', 'refreservation'),
            "volume_")

    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data


class ZVol_CreateForm(Form):
    zvol_name = forms.CharField(max_length=128, label=_('zvol name'))
    zvol_size = forms.CharField(
        max_length=128,
        label=_('Size for this zvol'),
        help_text=_('Example: 1g'))
    zvol_compression = forms.ChoiceField(
        choices=choices.ZFS_CompressionChoices,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Compression level'))
    zvol_sparse = forms.BooleanField(
        label=_('Sparse volume'),
        help_text=_(
            'Creates a sparse volume with no reservation, also kown '
            'as "thin provisioning". A "sparse volume" is a volume where the '
            'reservation is less then the volume size. Consequently, writes '
            'to a sparse volume can fail with ENOSPC when the pool is low on '
            'space. (NOT RECOMMENDED)'),
        required=False,
        initial=False,
    )
    zvol_blocksize = forms.CharField(
        label=_('Block size'),
        help_text=_(
            'The default blocksize for volumes is 8 Kbytes. Any power '
            'of 2 from 512 bytes to 128 Kbytes is valid.'),
        required=False,
        max_length=8,
    )

    advanced_fields = (
        'zvol_blocksize',
    )

    def __init__(self, *args, **kwargs):
        self.vol_name = kwargs.pop('vol_name')
        super(ZVol_CreateForm, self).__init__(*args, **kwargs)

    def clean_dataset_name(self):
        name = self.cleaned_data["zvol_name"]
        if not re.search(r'^[a-zA-Z0-9][a-zA-Z0-9_\-:.]*$', name):
            raise forms.ValidationError(_(
                "ZFS Volume names must begin with "
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
    mp_mode = UnixPermissionField(label=_('Mode'), required=False)
    mp_acl = forms.ChoiceField(
        label=_('Type of ACL'),
        choices=(
            ('unix', 'Unix'),
            ('windows', 'Windows'),
        ),
        initial='unix',
        widget=forms.widgets.RadioSelect(),
    )
    mp_recursive = forms.BooleanField(
        initial=False,
        required=False,
        label=_('Set permission recursively')
    )

    def __init__(self, *args, **kwargs):
        super(MountPointAccessForm, self).__init__(*args, **kwargs)

        path = kwargs.get('initial', {}).get('path', None)
        if path:
            if os.path.exists(os.path.join(path, ".windows")):
                self.fields['mp_acl'].initial = 'windows'
                self.fields['mp_mode'].widget.attrs['disabled'] = 'disabled'
            else:
                self.fields['mp_acl'].initial = 'unix'
            user, group = notifier().mp_get_owner(path)
            self.fields['mp_mode'].initial = "%.3o" % (
                notifier().mp_get_permission(path),
            )
            self.fields['mp_user'].initial = user
            self.fields['mp_group'].initial = group
        self.fields['mp_acl'].widget.attrs['onChange'] = "mpAclChange(this);"

    def clean(self):
        if (
            self.cleaned_data.get("mp_acl") == "unix"
            and
            not self.cleaned_data.get("mp_mode")
        ):
            self._errors['mp_mode'] = self.error_class([
                _("This field is required")
            ])
        return self.cleaned_data

    def commit(self, path='/mnt/'):

        notifier().mp_change_permission(
            path=path,
            user=self.cleaned_data['mp_user'],
            group=self.cleaned_data['mp_group'],
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
                new['task_begin'] = time(
                    hour=int(search.group("hour")),
                    minute=int(search.group("min")),
                    second=int(search.group("sec")))
            if "task_end" in new:
                search = HOUR.search(new['task_end'])
                new['task_end'] = time(
                    hour=int(search.group("hour")),
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

    def clean_task_byweekday(self):
        bwd = self.data.getlist('task_byweekday')
        return ','.join(bwd)

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
        notifier().zfs_mksnap(
            fs,
            str(self.cleaned_data['ms_name']),
            self.cleaned_data['ms_recursively'])


class CloneSnapshotForm(Form):
    cs_snapshot = forms.CharField(label=_('Snapshot'))
    cs_name = forms.CharField(label=_('Clone Name (must be on same volume)'))

    def __init__(self, *args, **kwargs):
        is_volume = kwargs.pop('is_volume', False)
        super(CloneSnapshotForm, self).__init__(*args, **kwargs)
        self.fields['cs_snapshot'].widget.attrs['readonly'] = True
        self.fields['cs_snapshot'].widget.attrs['class'] = (
            'dijitDisabled dijitTextBoxDisabled '
            'dijitValidationTextBoxDisabled')
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
        retval = notifier().zfs_clonesnap(
            snapshot,
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
        self.volume = kwargs.pop('volume')
        super(ZFSDiskReplacementForm, self).__init__(*args, **kwargs)
        if self.volume.vol_encrypt == 2:
            self.fields['pass'] = forms.CharField(
                label=_("Passphrase"),
                widget=forms.widgets.PasswordInput(),
            )
            self.fields['pass2'] = forms.CharField(
                label=_("Confirm Passphrase"),
                widget=forms.widgets.PasswordInput(),
            )

    def clean_pass2(self):
        passphrase = self.cleaned_data.get("pass")
        passphrase2 = self.cleaned_data.get("pass2")
        if passphrase != passphrase2:
            raise forms.ValidationError(
                _("Confirmation does not match passphrase")
            )
        passfile = tempfile.mktemp(dir='/tmp/')
        with open(passfile, 'w') as f:
            os.chmod(passfile, 600)
            f.write(passphrase)
        if not notifier().geli_testkey(self.volume, passphrase=passfile):
            self._errors['pass'] = self.error_class([
                _("Passphrase is not valid")
            ])
        os.unlink(passfile)
        return passphrase

    def done(self, fromdisk, label):
        devname = self.cleaned_data['volume_disks']
        passphrase = self.cleaned_data.get("pass")
        if passphrase is not None:
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                os.chmod(passfile, 600)
                f.write(passphrase)
        else:
            passfile = None

        with transaction.commit_on_success():
            if devname != fromdisk:
                rv = notifier().zfs_replace_disk(
                    self.volume,
                    label,
                    devname,
                    passphrase=passfile
                )
            else:
                rv = notifier().zfs_replace_disk(
                    self.volume,
                    label,
                    fromdisk,
                    passphrase=passfile
                )
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
    remote_port = forms.IntegerField(
        label=_("Remote port"),
        initial=22,
        required=False,
    )
    remote_dedicateduser_enabled = forms.BooleanField(
        label=_("Dedicated User Enabled"),
        help_text=_("If disabled then root will be used for replication."),
        required=False,
    )
    remote_dedicateduser = UserField(
        label=_("Dedicated User"),
        required=False,
    )
    remote_fast_cipher = forms.BooleanField(
        label=_("Enable High Speed Ciphers"),
        initial=False,
        required=False,
        help_text=_(
            "Enabling this may increase transfer speed on high "
            "speed/low latency local networks.  It uses less secure encryption"
            " algorithms than the defaults, which makes it less desirable on "
            "untrusted networks."),
    )
    remote_hostkey = forms.CharField(
        label=_("Remote hostkey"),
        widget=forms.Textarea(),
    )

    class Meta:
        model = models.Replication
        exclude = ('repl_lastsnapshot', 'repl_remote')
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
                new['repl_begin'] = time(
                    hour=int(search.group("hour")),
                    minute=int(search.group("min")),
                    second=int(search.group("sec")))
            if "repl_end" in new:
                search = HOUR.search(new['repl_end'])
                new['repl_end'] = time(
                    hour=int(search.group("hour")),
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

        self.fields['remote_dedicateduser_enabled'].widget.attrs['onClick'] = (
            'toggleGeneric("id_remote_dedicateduser_enabled", '
            '["id_remote_dedicateduser"], true);')

        if repl and repl.id:
            self.fields['remote_hostname'].initial = (
                repl.repl_remote.ssh_remote_hostname)
            self.fields['remote_port'].initial = (
                repl.repl_remote.ssh_remote_port)
            self.fields['remote_dedicateduser_enabled'].initial = (
                repl.repl_remote.ssh_remote_dedicateduser_enabled)
            self.fields['remote_dedicateduser'].initial = (
                repl.repl_remote.ssh_remote_dedicateduser)
            self.fields['remote_fast_cipher'].initial = (
                repl.repl_remote.ssh_fast_cipher)
            self.fields['remote_hostkey'].initial = (
                repl.repl_remote.ssh_remote_hostkey)
            if not repl.repl_remote.ssh_remote_dedicateduser_enabled:
                self.fields['remote_dedicateduser'].widget.attrs[
                    'disabled'] = 'disabled'

        else:
            if not self.data.get("remote_dedicateduser_enabled", False):
                self.fields['remote_dedicateduser'].widget.attrs[
                    'disabled'] = 'disabled'

    def clean_remote_port(self):
        port = self.cleaned_data.get('remote_port')
        if not port:
            return 22
        return port

    def clean_remote_dedicateduser(self):
        en = self.cleaned_data.get("remote_dedicateduser_enabled")
        user = self.cleaned_data.get("remote_dedicateduser")
        if en and user is None:
            raise forms.ValidationError("You must select a valid user")
        return user

    def save(self):
        if self.instance.id is None:
            r = models.ReplRemote()
        else:
            r = self.instance.repl_remote
        r.ssh_remote_hostname = self.cleaned_data.get("remote_hostname")
        r.ssh_remote_hostkey = self.cleaned_data.get("remote_hostkey")
        r.ssh_remote_dedicateduser_enabled = self.cleaned_data.get(
            "remote_dedicateduser_enabled")
        r.ssh_remote_dedicateduser = self.cleaned_data.get(
            "remote_dedicateduser")
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
    mark_new = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Mark the disks as new (destroy data)"),
    )

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        services = kwargs.pop('services', {})
        super(VolumeExport, self).__init__(*args, **kwargs)
        if services.keys():
            self.fields['cascade'] = forms.BooleanField(
                initial=True,
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
            self.fields['cascade'] = forms.BooleanField(
                initial=False,
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
                attrs={
                    'numChoices': 31,
                    'start': 1,
                    'label': _("day of month")},
            ),
            'scrub_dayweek': forms.CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES),
            'scrub_month': forms.CheckboxSelectMultiple(
                choices=choices.MONTHS_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super(ScrubForm, self).__init__(*args, **kwargs)
        mchoicefield(self, 'scrub_month', [
            1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
        ])
        mchoicefield(self, 'scrub_dayweek', [
            1, 2, 3, 4, 5, 6, 7
        ])

    def clean_scrub_month(self):
        m = self.data.getlist("scrub_month")
        if len(m) == 12:
            return '*'
        m = ",".join(m)
        return m

    def clean_scrub_dayweek(self):
        w = self.data.getlist("scrub_dayweek")
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
                os.chmod(passfile, 600)
                f.write(passphrase)
        else:
            passfile = None
        notifier().geli_passphrase(volume, passfile, rmrecovery=True)
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
            'toggleGeneric("id_remove", ["id_passphrase", '
            '"id_passphrase2"], false);')
        if self.data.get("remove", False):
            self.fields['passphrase'].widget.attrs['disabled'] = 'disabled'
            self.fields['passphrase2'].widget.attrs['disabled'] = 'disabled'

        user = User.objects.filter(
            is_superuser=True,
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
                os.chmod(passfile, 600)
                f.write(passphrase)
        else:
            passfile = None
        notifier().geli_passphrase(volume, passfile)
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
        required=False,
    )
    key = FileField(
        label=_("Recovery Key"),
        required=False,
    )
    services = forms.MultipleChoiceField(
        label=_("Restart services"),
        widget=forms.widgets.CheckboxSelectMultiple(),
        initial=['cifs', 'afp', 'nfs', 'iscsitarget'],
        choices=(
            ('afp', _('AFP')),
            ('cifs', _('CIFS')),
            ('iscsitarget', _('iSCSI')),
            ('nfs', _('NFS'))
        ),
        required=False,
    )

    def clean(self):
        passphrase = self.cleaned_data.get("passphrase")
        key = self.cleaned_data.get("key")
        log.error("%r", key)
        if not passphrase and key is None:
            self._errors['__all__'] = self.error_class([
                _("You need either a passphrase or a recovery key to unlock")
            ])
        return self.cleaned_data

    def done(self, volume):
        passphrase = self.cleaned_data.get("passphrase")
        key = self.cleaned_data.get("key")
        if passphrase:
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                os.chmod(passfile, 600)
                f.write(passphrase)
            failed = notifier().geli_attach(volume, passphrase=passfile)
            os.unlink(passfile)
        elif key is not None:
            keyfile = tempfile.mktemp(dir='/tmp/')
            with open(keyfile, 'wb') as f:
                os.chmod(keyfile, 600)
                f.write(key.read())
            failed = notifier().geli_attach(
                volume,
                passphrase=None,
                key=keyfile)
            os.unlink(keyfile)
        else:
            raise ValueError("Need a passphrase or recovery key")
        zimport = notifier().zfs_import(volume.vol_name, id=volume.vol_guid)
        if not zimport:
            if failed > 0:
                msg = _(
                    "Volume could not be imported: %d devices failed to "
                    "decrypt"
                ) % failed
            else:
                msg = _("Volume could not be imported")
            raise MiddlewareError(msg)
        notifier().sync_encrypted(volume=volume)

        _notifier = notifier()
        for svc in self.cleaned_data.get("services"):
            _notifier.restart(svc)


class KeyForm(forms.Form):

    adminpw = forms.CharField(
        label=_("Admin password"),
        widget=forms.widgets.PasswordInput(),
    )

    def __init__(self, *args, **kwargs):
        super(KeyForm, self).__init__(*args, **kwargs)

        user = User.objects.filter(
            is_superuser=True,
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


class ReKeyForm(KeyForm):

    def __init__(self, *args, **kwargs):
        self.volume = kwargs.pop('volume')
        super(ReKeyForm, self).__init__(*args, **kwargs)
        if self.volume.vol_encrypt == 2:
            self.fields['passphrase'] = forms.CharField(
                label=_("Passphrase"),
                widget=forms.widgets.PasswordInput(),
            )

    def done(self):
        passphrase = self.cleaned_data.get("passphrase")
        if passphrase:
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                os.chmod(passfile, 600)
                f.write(passphrase)
            passphrase = passfile
        notifier().geli_rekey(self.volume, passphrase)
        if passphrase:
            os.unlink(passfile)
