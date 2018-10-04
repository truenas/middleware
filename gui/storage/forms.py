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
from collections import defaultdict
from datetime import datetime, time

import base64
import logging
import os
import re
import ssl
import tempfile
import uuid

from formtools.wizard.views import SessionWizardView
from django.core.files.storage import FileSystemStorage
from django.core.urlresolvers import reverse
from django.forms import FileField
from django.forms.formsets import BaseFormSet, formset_factory
from django.http import HttpResponse, QueryDict
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ungettext

from dojango import forms
from dojango.forms import CheckboxSelectMultiple
from freenasUI import choices
from freenasUI.account.models import bsdUsers
from freenasUI.common import humanize_number_si
from freenasUI.common.forms import ModelForm, Form, mchoicefield
from freenasUI.freeadmin.apppool import appPool
from freenasUI.freeadmin.forms import (
    CronMultiple, UserField, GroupField, WarningSelect,
    PathField, SizeField,
)
from freenasUI.freeadmin.utils import key_order
from freenasUI.freeadmin.views import JsonResp
from freenasUI.middleware.client import client, ClientException, ValidationErrors
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.form import MiddlewareModelForm
from freenasUI.middleware.notifier import notifier
from freenasUI.middleware.util import JobAborted, JobFailed, upload_job_and_wait
from freenasUI.services.models import iSCSITargetExtent
from freenasUI.storage import models
from freenasUI.storage.widgets import UnixPermissionField
from freenasUI.support.utils import dedup_enabled
from pyVim import connect, task as VimTask
from pyVmomi import vim


attrs_dict = {'class': 'required', 'maxHeight': 200}

log = logging.getLogger('storage.forms')

DEDUP_WARNING = _(
    "Enabling dedup can drastically reduce performance and<br />"
    "affect the ability to access data. Compression usually<br />"
    "offers similar space savings with much lower<br />"
    "performance impact and overhead.<br />")

RE_HOUR = re.compile(r'(?P<hour>\d{2}):(?P<min>\d{2}):(?P<sec>\d{2})')


def fix_time_fields(data, names):
    for name in names:
        if name not in data:
            continue
        search = RE_HOUR.search(data[name])
        data[name] = time(
            hour=int(search.group("hour")),
            minute=int(search.group("min")),
            second=int(search.group("sec")),
        )


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
        else:
            self.dtype = devname
            self.number = None
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
        return '<Disk: %s>' % str(self)

    def __str__(self):
        extra = ' %s' % (self.serial,) if self.serial else ''
        return '%s (%s)%s' % (self.dev, humanize_number_si(self.size), extra)

    def __iter__(self):
        yield self.dev
        yield str(self)


def _inherit_choices(choices, inheritvalue):
    nchoices = []
    for value, name in choices:
        if value == 'inherit':
            name += ' (%s)' % inheritvalue
        nchoices.append((value, name))
    return nchoices


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
        if vname in ('log',):
            raise forms.ValidationError(_('\"log\" is a reserved word and thus cannot be used'))
        elif re.search(r'^c[0-9].*', vname) or \
                re.search(r'^mirror.*', vname) or \
                re.search(r'^spare.*', vname) or \
                re.search(r'^raidz.*', vname):
            raise forms.ValidationError(_(
                "The volume name may NOT start with c[0-9], mirror, "
                "raidz or spare"
            ))
        return vname


class VolumeManagerForm(VolumeMixin, Form):
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
        self._formset.pform = self
        fsvalid = self._formset.is_valid()
        if not fsvalid:
            nonformerrors = self._formset.non_form_errors()
            if nonformerrors:
                self._errors['__all__'] = self.error_class(nonformerrors)
        return valid and fsvalid

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
        encryption = self.cleaned_data.get("encryption", False)

        volume = models.Volume.objects.filter(vol_name=volume_name)
        if volume.count() > 0:
            add = volume[0]
        else:
            add = False

        topology = defaultdict(list)
        for i, form in enumerate(formset):
            if not form.cleaned_data.get('vdevtype'):
                continue

            vdevtype = form.cleaned_data.get("vdevtype")
            if vdevtype in ('raidz', 'raidz2', 'raidz3', 'mirror', 'stripe'):
                topology['data'].append({
                    'type': 'RAIDZ1' if vdevtype == 'raidz' else vdevtype.upper(),
                    'disks': form.cleaned_data.get("disks"),
                })
            elif vdevtype == 'cache':
                topology['cache'].append({
                    'type': 'STRIPE',
                    'disks': form.cleaned_data.get("disks"),
                })
            elif vdevtype == 'log':
                topology['log'].append({
                    'type': 'STRIPE',
                    'disks': form.cleaned_data.get("disks"),
                })
            elif vdevtype == 'log mirror':
                topology['log'].append({
                    'type': 'MIRROR',
                    'disks': form.cleaned_data.get("disks"),
                })
            elif vdevtype == 'spare':
                topology['spares'].extend(form.cleaned_data.get("disks"))

        with client as c:
            try:
                if add:
                    pool = c.call('pool.update', add.id, {'topology': topology}, job=True)
                else:
                    pool = c.call('pool.create', {
                        'name': volume_name,
                        'encryption': encryption,
                        'topology': topology,
                    }, job=True)
            except ValidationErrors as e:
                self._errors['__all__'] = self.error_class([err.errmsg for err in e.errors])
                return False

        # ModelForm compatibility layer for API framework
        self.instance = self.volume = models.Volume.objects.get(pk=pool['id'])

        return volume


class VolumeVdevForm(Form):
    vdevtype = forms.CharField(
        max_length=20,
    )
    disks = forms.CharField(
        max_length=800,
        widget=forms.widgets.SelectMultiple(),
    )

    def clean_disks(self):
        # TODO: Safe?
        disks = eval(self.cleaned_data.get("disks"))
        return disks

    def clean(self):
        if (
            self.cleaned_data.get("vdevtype") == "log" and
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


class ZFSVolumeWizardForm(Form):
    volume_name = forms.CharField(
        max_length=30,
        label=_('Volume name'),
        required=False)
    volume_disks = forms.MultipleChoiceField(
        choices=(),
        widget=forms.SelectMultiple(attrs=attrs_dict),
        label=_('Member disks'),
        required=False)
    group_type = forms.ChoiceField(
        choices=(),
        widget=forms.RadioSelect(attrs=attrs_dict),
        required=False)
    enc = forms.BooleanField(
        label=_('Encryption'),
        required=False,
    )
    encini = forms.BooleanField(
        label=_('Initialize Safely'),
        required=False,
    )
    dedup = forms.ChoiceField(
        label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP,
        initial="off",
    )

    def __init__(self, *args, **kwargs):
        super(ZFSVolumeWizardForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        qs = models.Volume.objects.filter()
        if qs.exists():
            self.fields['volume_add'] = forms.ChoiceField(
                label=_('Volume add'),
                required=False)
            self.fields['volume_add'].choices = [
                ('', '-----')
            ] + [(x.vol_name, x.vol_name) for x in qs]
            self.fields['volume_add'].widget.attrs['onChange'] = (
                'zfswizardcheckings(true);')

        self.fields['enc'].widget.attrs['onChange'] = (
            'zfswizardcheckings(true);')

        grouptype_choices = (
            ('mirror', 'mirror'),
            ('stripe', 'stripe'),
        )
        if "volume_disks" in self.data:
            disks = self.data.getlist("volume_disks")
        else:
            disks = []
        if len(disks) >= 3:
            grouptype_choices += (('raidz', 'RAID-Z'), )
        if len(disks) >= 4:
            grouptype_choices += (('raidz2', 'RAID-Z2'), )
        if len(disks) >= 5:
            grouptype_choices += (('raidz3', 'RAID-Z3'), )
        self.fields['group_type'].choices = grouptype_choices

        # dedup = _dedup_enabled()
        dedup = True
        if not dedup:
            self.fields['dedup'].widget.attrs['readonly'] = True
            self.fields['dedup'].widget.attrs['class'] = (
                'dijitSelectDisabled dijitDisabled')

    def _populate_disk_choices(self):

        disks = []
        _n = notifier()

        if hasattr(_n, 'failover_status'):
            from freenasUI.truenas import ses
            encs = ses.Enclosures()
        else:
            encs = None

        # Grab disk list
        # Root device already ruled out
        for disk, info in list(_n.get_disks().items()):
            serial = info.get('ident', '')
            if encs:
                try:
                    ele = encs.find_device_slot(info['devname'])
                    serial = '%s/ %s' % (
                        '%s ' if serial else '',
                        ele.enclosure.devname,
                    )
                except Exception:
                    pass
            disks.append(Disk(
                info['devname'],
                info['capacity'],
                serial=serial,
            ))

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
            raise forms.ValidationError(_(
                "The volume name must start with "
                "letters and may include numbers, \"-\", \"_\" and \".\" ."))
        if models.Volume.objects.filter(vol_name=vname).exists():
            raise forms.ValidationError(_(
                "A volume with that name already exists."
            ))
        return vname

    def clean_group_type(self):
        if 'volume_disks' not in self.cleaned_data or \
                len(self.cleaned_data['volume_disks']) > 1 and \
                self.cleaned_data['group_type'] in (None, ''):
            raise forms.ValidationError(_("This field is required."))
        return self.cleaned_data['group_type']

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

        if len(disks) == 0 and models.Volume.objects.filter(
                vol_name=volume_name).count() == 0:
            msg = _("This field is required")
            self._errors["volume_disks"] = self.error_class([msg])
            del cleaned_data["volume_disks"]

        if volume_name in ('log',):
            msg = _("\"log\" is a reserved word and thus cannot be used")
            self._errors["volume_name"] = self.error_class([msg])
            cleaned_data.pop("volume_name", None)
        elif re.search(r'^c[0-9].*', volume_name) or \
                re.search(r'^mirror.*', volume_name) or \
                re.search(r'^spare.*', volume_name) or \
                re.search(r'^raidz.*', volume_name):
            msg = _(
                "The volume name may NOT start with c[0-9], mirror, "
                "raidz or spare"
            )
            self._errors["volume_name"] = self.error_class([msg])
            cleaned_data.pop("volume_name", None)

        return cleaned_data

    def done(self, request, events):
        # Construct and fill forms into database.
        volume_name = (
            self.cleaned_data.get("volume_name") or
            self.cleaned_data.get("volume_add")
        )
        disk_list = self.cleaned_data['volume_disks']
        dedup = self.cleaned_data.get("dedup", False)
        if self.cleaned_data.get("enc", False):
            volume_encrypt = True
        else:
            volume_encrypt = False

        if (len(disk_list) < 2):
            group_type = 'stripe'
        else:
            group_type = self.cleaned_data['group_type']
        if group_type == 'raidz':
            group_type = 'raidz1'
        group_type = group_type.upper()

        vols = models.Volume.objects.filter(vol_name=volume_name)
        if vols.count() == 1:
            add = vols[0]
        else:
            add = False

        topology = defaultdict(list)
        topology['data'].append({'type': group_type, 'disks': disk_list})

        zpoolfields = re.compile(r'zpool_(.+)')
        for i, gtype in list(request.POST.items()):
            if zpoolfields.match(i):
                if gtype == 'none':
                    continue
                disk = zpoolfields.search(i).group(1)
                # if this is a log vdev we need to mirror it for safety
                if gtype in topology:
                    if gtype == 'log':
                        topology[gtype][0]['type'] = 'MIRROR'
                    topology[gtype][0]['disks'].append(disk)
                else:
                    topology[gtype].append({
                        'type': 'STRIPE',
                        'disks': [disk],
                    })

        with client as c:
            try:
                if add:
                    c.call('pool.update', add.id, {'topology': topology}, job=True)
                else:
                    c.call('pool.create', {
                        'name': volume_name,
                        'encryption': volume_encrypt,
                        'topology': topology,
                        'deduplication': dedup.upper(),
                    }, job=True)
            except ValidationErrors as e:
                self._errors['__all__'] = self.error_class([err.errmsg for err in e.errors])
                return False

        super(ZFSVolumeWizardForm, self).done(request, events)
        return True


class VolumeImportForm(Form):

    volume_disks = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs=attrs_dict),
        label=_('Member disk'),
        help_text=_("This is the disk with the non-zfs filesystem. "
                    "It will be mounted, its data copied over to the path "
                    "specified in the 'Destination' field below and "
                    "then unmounted. Importing non-zfs disks permanently "
                    "as a Volume is deprecated"),
    )
    volume_fstype = forms.ChoiceField(
        choices=((x, x) for x in ('UFS', 'NTFS', 'MSDOSFS', 'EXT2FS')),
        widget=forms.RadioSelect(attrs=attrs_dict),
        label=_('File System type'),
    )
    volume_msdosfs_locale = forms.ChoiceField(
        label=_("MSDOSFS locale"),
        choices=(),
        widget=forms.Select(attrs=attrs_dict),
        required=False,
    )

    volume_dest_path = PathField(
        label=_("Destination"),
        help_text=_("This must be a dataset/folder in an existing Volume"),
    )

    def __init__(self, *args, **kwargs):
        super(VolumeImportForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        with client as c:
            self.fields['volume_msdosfs_locale'].choices = [('', 'Default')] + [
                (locale, locale)
                for locale in c.call('pool.import_disk_msdosfs_locales')
            ]

    def _populate_disk_choices(self):

        used_disks = []
        for v in models.Volume.objects.all():
            used_disks.extend(v.get_disks())

        qs = iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk')
        diskids = [i[0] for i in qs.values_list('iscsi_target_extent_path')]
        used_disks.extend([d.disk_name for d in models.Disk.objects.filter(
            disk_identifier__in=diskids)])

        n = notifier()
        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        _parts = n.get_partitions()
        for name, part in list(_parts.items()):
            for i in used_disks:
                if re.search(r'^%s([ps]|$)' % i, part['devname']) is not None:
                    _parts.pop(name, None)

        parts = []
        for name, part in list(_parts.items()):
            parts.append(Disk(part['devname'], part['capacity']))

        choices = sorted(parts)
        choices = [tuple(p) for p in choices]
        return choices

    def clean(self):
        cleaned_data = self.cleaned_data
        devpath = "/dev/%s" % (cleaned_data.get('volume_disks', []), )
        isvalid = notifier().precheck_partition(
            devpath,
            cleaned_data.get('volume_fstype', ''))
        if not isvalid:
            msg = _(
                "The selected disks were not verified for these import "
                "rules. Filesystem check failed."
            )
            self._errors["volume_fstype"] = self.error_class([msg])
        path = cleaned_data.get("volume_dest_path")
        if path is None or not os.path.exists(path):
            self._errors["volume_dest_path"] = self.error_class(
                [_("The path %s does not exist.\
                    This must be a dataset/folder in an existing Volume" % path)])
        return cleaned_data


def show_decrypt_condition(wizard):
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
                "<html><body><textarea>" +
                response.rendered_content +
                "</textarea></boby></html>")
        return response

    def done(self, form_list, **kwargs):

        appPool.hook_form_init('AutoImportWizard', self, form_list, **kwargs)

        cdata = self.get_cleaned_data_for_step('1') or {}
        enc_disks = cdata.get("disks", [])
        key = cdata.get("key")
        if key:
            key.seek(0)
        passphrase = cdata.get("passphrase")

        cdata = self.get_cleaned_data_for_step('2') or {}
        vol = cdata['volume']

        arg = {
            'guid': vol['guid'],
            'devices': enc_disks,
            'passphrase': passphrase,
        }

        if enc_disks:
            try:
                upload_job_and_wait(key, 'pool.import_pool', arg)
            except JobAborted:
                raise MiddlewareError(_('Import job aborted'))
            except JobFailed as e:
                raise MiddlewareError(_('Import job failed: %s') % e.value)
        else:
            with client as c:
                c.call('pool.import_pool', arg, job=True)

        events = ['loadalert()']
        appPool.hook_form_done('AutoImportWizard', self, self.request, events)

        return JsonResp(
            self.request,
            message=str(_("Volume imported")),
            events=events,
        )


class AutoImportChoiceForm(Form):
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
            try:
                _notifier.geli_detach(dev)
            except Exception as ee:
                log.warn(str(ee))


class AutoImportDecryptForm(Form):
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
        with client as c:
            return [
                (i['dev'], i['name'])
                for i in c.call('disk.get_encrypted', {'unused': True})
            ]

    def clean(self):
        key = self.cleaned_data.get("key")
        if not key:
            return self.cleaned_data

        disks = self.cleaned_data.get("disks")
        if not disks:
            return self.cleaned_data

        passphrase = self.cleaned_data.get("passphrase")

        try:
            upload_job_and_wait(key, 'disk.decrypt', disks, passphrase)
        except JobFailed as e:
            self._errors['__all__'] = self.error_class([e.value])
        except JobAborted:
            self._errors['__all__'] = self.error_class([_('Decrypt job aborted')])

        return self.cleaned_data


class VolumeAutoImportForm(Form):

    volume_id = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs=attrs_dict),
        label=_('Volume'))

    def __init__(self, *args, **kwargs):
        super(VolumeAutoImportForm, self).__init__(*args, **kwargs)
        self.fields['volume_id'].choices = self._volume_choices()

    @classmethod
    def _volume_choices(cls):
        volchoices = {}
        with client as c:
            for p in c.call('pool.import_find'):
                volchoices[f'{p["name"]}|{p["guid"]}'] = f'{p["name"]} [id={p["guid"]}]'
        return list(volchoices.items())

    def clean(self):
        cleaned_data = self.cleaned_data
        with client as c:
            pools = c.call('pool.import_find')
        volume_name, guid = cleaned_data.get('volume_id', '|').split('|', 1)
        for pool in pools:
            if pool['name'] == volume_name:
                if (guid and guid == pool['guid']) or not guid:
                    cleaned_data['volume'] = pool
                    break

        if cleaned_data.get('volume', None) is None:
            self._errors['__all__'] = self.error_class([
                _("You must select a volume."),
            ])

        else:
            if models.Volume.objects.filter(
                    vol_name=cleaned_data['volume']['name']).count() > 0:
                msg = _("You already have a volume with same name")
                self._errors["volume_id"] = self.error_class([msg])
                del cleaned_data["volume_id"]

        return cleaned_data


class DiskFormPartial(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "disk_"
    middleware_attr_schema = "disk_"
    middleware_plugin = "disk"
    is_singletone = False

    disk_passwd2 = forms.CharField(
        max_length=50,
        label=_("Confirm SED Password"),
        widget=forms.widgets.PasswordInput(),
        required=False,
    )

    disk_reset_password = forms.BooleanField(
        label='Reset Password',
        required=False,
        initial=False,
        help_text=_('Click this box to reset SED password'),
    )

    class Meta:
        model = models.Disk
        widgets = {
            'disk_passwd': forms.widgets.PasswordInput(render_value=False)
        }
        exclude = (
            'disk_transfermode',  # This option isn't used anywhere
        )

    def __init__(self, *args, **kwargs):
        super(DiskFormPartial, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
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

            self.fields['disk_reset_password'].widget.attrs['onChange'] = (
                'toggleGeneric("id_disk_reset_password", ["id_disk_passwd",'
                ' "id_disk_passwd2"], false);'
            )

    def clean_disk_name(self):
        return self.instance.disk_name

    def clean_disk_passwd2(self):
        password1 = self.cleaned_data.get("disk_passwd")
        password2 = self.cleaned_data.get("disk_passwd2")
        if password1 != password2:
            raise forms.ValidationError(_("The two password fields didn't match."))
        return password2

    def middleware_clean(self, data):
        self.instance.id = self.instance.pk
        data.pop('name')
        data.pop('passwd2', None)
        reset_passwd = data.pop('reset_password', None)
        data.pop('serial')

        sed_passwd = data.pop('passwd', '')
        if reset_passwd:
            data['passwd'] = ''
        elif sed_passwd:
            data['passwd'] = sed_passwd

        for key in ['acousticlevel', 'advpowermgmt', 'hddstandby']:
            if data.get(key):
                data[key] = data[key].upper()
        return data


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
        self.fields['ids'].initial = ','.join([str(d.pk) for d in self._disks])

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

        for key, val in list(initials.items()):
            self.fields[key].initial = val

    def save(self):
        data = {
            # This is not a choice field, an empty value should reset all
            'smartoptions': self.cleaned_data.get('disk_smartoptions'),
            'togglesmart': self.cleaned_data.get('disk_togglesmart')
        }

        for opt in (
                'disk_hddstandby',
                'disk_advpowermgmt',
                'disk_acousticlevel',
        ):
            if self.cleaned_data.get(opt):
                data[opt[5:]] = self.cleaned_data.get(opt).upper()

        primary_keys = [str(d.pk) for d in self._disks]

        with client as c:
            c.call('core.bulk', 'disk.update', [[key, data] for key in primary_keys], job=True)

        return models.Disk.objects.filter(pk__in=primary_keys)


DATASET_COMMON_MAPPING = [
    ('dataset_comments', 'comments', None),
    ('dataset_sync', 'sync', str.upper),
    ('dataset_compression', 'compression', str.upper),
    ('dataset_share_type', 'share_type', str.upper),
    ('dataset_atime', 'atime', str.upper),
    ('dataset_refquota', 'refquota', lambda v: v or None),
    ('refquota_warning', 'refquota_warning', None),
    ('refquota_critical', 'refquota_critical', None),
    ('dataset_quota', 'quota', lambda v: v or None),
    ('quota_warning', 'quota_warning', None),
    ('quota_critical', 'quota_critical', None),
    ('dataset_refreservation', 'refreservation', None),
    ('dataset_reservation', 'reservation', None),
    ('dataset_dedup', 'deduplication', str.upper),
    ('dataset_readonly', 'readonly', str.upper),
    ('dataset_exec', 'exec', str.upper),
    ('dataset_recordsize', 'recordsize', str.upper),
]


class ZFSDatasetCommonForm(Form):
    dataset_comments = forms.CharField(
        max_length=1024,
        label=_('Comments'),
        required=False)
    dataset_sync = forms.ChoiceField(
        choices=choices.ZFS_SyncChoices,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Sync'),
        initial=choices.ZFS_SyncChoices[0][0])
    dataset_compression = forms.ChoiceField(
        choices=choices.ZFS_CompressionChoices,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Compression level'),
        initial=choices.ZFS_CompressionChoices[0][0])
    dataset_share_type = forms.ChoiceField(
        choices=choices.SHARE_TYPE_CHOICES,
        widget=forms.Select(attrs=attrs_dict),
        label=_('Share type'),
        initial=choices.SHARE_TYPE_CHOICES[0][0])
    dataset_atime = forms.ChoiceField(
        choices=choices.ZFS_AtimeChoices,
        widget=forms.RadioSelect(attrs=attrs_dict),
        label=_('Enable atime'),
        initial=choices.ZFS_AtimeChoices[0][0])
    dataset_refquota = SizeField(
        required=False,
        initial=0,
        label=_('Quota for this dataset'),
        help_text=_('0=Unlimited; example: 1 GiB'))
    refquota_warning = forms.CharField(
        required=False,
        initial=None,
        label=_('Quota warning alert at, %'),
        help_text=_('0=Disabled, blank=inherit'))
    refquota_critical = forms.CharField(
        required=False,
        initial=None,
        label=_('Quota critical alert at, %'),
        help_text=_('0=Disabled, blank=inherit'))
    dataset_quota = SizeField(
        required=False,
        initial=0,
        label=_('Quota for this dataset and all children'),
        help_text=_('0=Unlimited; example: 1 GiB'))
    quota_warning = forms.CharField(
        required=False,
        initial=None,
        label=_('Quota warning alert at, %'),
        help_text=_('0=Disabled, blank=inherit'))
    quota_critical = forms.CharField(
        required=False,
        initial=None,
        label=_('Quota critical alert at, %'),
        help_text=_('0=Disabled, blank=inherit'))
    dataset_refreservation = SizeField(
        required=False,
        initial=0,
        label=_('Reserved space for this dataset'),
        help_text=_('0=None; example: 1 GiB'))
    dataset_reservation = SizeField(
        required=False,
        initial=0,
        label=_('Reserved space for this dataset and all children'),
        help_text=_('0=None; example: 1 GiB'))
    dataset_dedup = forms.ChoiceField(
        label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP_INHERIT,
        widget=WarningSelect(text=DEDUP_WARNING),
        initial="inherit",
    )
    dataset_readonly = forms.ChoiceField(
        label=_('Read-Only'),
        choices=choices.ZFS_ReadonlyChoices,
        initial=choices.ZFS_ReadonlyChoices[0][0],
    )
    dataset_exec = forms.ChoiceField(
        label=_('Exec'),
        choices=choices.ZFS_ExecChoices,
        initial=choices.ZFS_ExecChoices[0][0],
    )
    dataset_recordsize = forms.ChoiceField(
        label=_('Record Size'),
        choices=choices.ZFS_RECORDSIZE,
        initial=choices.ZFS_RECORDSIZE[0][0],
        required=False,
        help_text=_(
            "Specifies a suggested block size for files in the file system. "
            "This property is designed solely for use with database workloads "
            "that access files in fixed-size records.  ZFS automatically tunes "
            "block sizes according to internal algorithms optimized for "
            "typical access patterns."
        )
    )

    advanced_fields = (
        'dataset_readonly',
        'dataset_refquota',
        'refquota_warning',
        'refquota_critical',
        'dataset_quota',
        'quota_warning',
        'quota_critical',
        'dataset_refreservation',
        'dataset_reservation',
        'dataset_recordsize',
        'dataset_exec',
    )

    def __init__(self, *args, fs=None, **kwargs):
        self._fs = fs
        super(ZFSDatasetCommonForm, self).__init__(*args, **kwargs)

        if hasattr(self, 'parentdata'):
            self.fields['dataset_atime'].choices = _inherit_choices(
                choices.ZFS_AtimeChoices,
                self.parentdata['atime']['value'].lower()
            )
            self.fields['dataset_sync'].choices = _inherit_choices(
                choices.ZFS_SyncChoices,
                self.parentdata['sync']['value'].lower()
            )
            self.fields['dataset_compression'].choices = _inherit_choices(
                choices.ZFS_CompressionChoices,
                self.parentdata['compression']['value'].lower()
            )
            self.fields['dataset_dedup'].choices = _inherit_choices(
                choices.ZFS_DEDUP_INHERIT,
                self.parentdata['deduplication']['value'].lower()
            )
            self.fields['dataset_readonly'].choices = _inherit_choices(
                choices.ZFS_ReadonlyChoices,
                self.parentdata['readonly']['value'].lower()
            )
            self.fields['dataset_exec'].choices = _inherit_choices(
                choices.ZFS_ExecChoices,
                self.parentdata['exec']['value'].lower()
            )
            self.fields['dataset_recordsize'].choices = _inherit_choices(
                choices.ZFS_RECORDSIZE,
                self.parentdata['recordsize']['value']
            )

        if not dedup_enabled():
            self.fields['dataset_dedup'].widget.attrs['readonly'] = True
            self.fields['dataset_dedup'].widget.attrs['class'] = (
                'dijitSelectDisabled dijitDisabled')
            self.fields['dataset_dedup'].widget.text = mark_safe(
                '<span style="color: red;">Dedup feature not activated. '
                'Contact <a href="mailto:truenas-support@ixsystems.com?subject'
                '=ZFS Deduplication Activation">TrueNAS Support</a> for '
                'assistance.</span><br />'
            )

    def clean_quota_warning(self):
        if self.cleaned_data["quota_warning"]:
            if not self.cleaned_data["quota_warning"].isdigit():
                raise forms.ValidationError("Not a valid integer")

            if not (0 <= int(self.cleaned_data["quota_warning"]) <= 100):
                raise forms.ValidationError("Should be between 0 and 100")

            return int(self.cleaned_data["quota_warning"])

        return 'INHERIT'

    def clean_quota_critical(self):
        if self.cleaned_data["quota_critical"]:
            if not self.cleaned_data["quota_critical"].isdigit():
                raise forms.ValidationError("Not a valid integer")

            if not (0 <= int(self.cleaned_data["quota_critical"]) <= 100):
                raise forms.ValidationError("Should be between 0 and 100")

            return int(self.cleaned_data["quota_critical"])

        return 'INHERIT'

    def clean_refquota_warning(self):
        if self.cleaned_data["refquota_warning"]:
            if not self.cleaned_data["refquota_warning"].isdigit():
                raise forms.ValidationError("Not a valid integer")

            if not (0 <= int(self.cleaned_data["refquota_warning"]) <= 100):
                raise forms.ValidationError("Should be between 0 and 100")

            return int(self.cleaned_data["refquota_warning"])

        return 'INHERIT'

    def clean_refquota_critical(self):
        if self.cleaned_data["refquota_critical"]:
            if not self.cleaned_data["refquota_critical"].isdigit():
                raise forms.ValidationError("Not a valid integer")

            if not (0 <= int(self.cleaned_data["refquota_critical"]) <= 100):
                raise forms.ValidationError("Should be between 0 and 100")

            return int(self.cleaned_data["refquota_critical"])

        return 'INHERIT'


DATASET_IMMUTABLE_MAPPING = [
    ('dataset_case_sensitivity', 'casesensitivity', str.upper),
]


class ZFSDatasetCreateForm(ZFSDatasetCommonForm):
    dataset_name = forms.CharField(
        max_length=128,
        label=_('Dataset Name'))
    dataset_case_sensitivity = forms.ChoiceField(
        choices=choices.CASE_SENSITIVITY_CHOICES,
        initial=choices.CASE_SENSITIVITY_CHOICES[0][0],
        widget=forms.Select(attrs=attrs_dict),
        label=_('Case Sensitivity'))

    field_order = ['dataset_name']

    def __init__(self, *args, fs=None, **kwargs):
        # Common form expects a parentdata
        # We use `fs` as parent data because thats where we inherit props from
        with client as c:
            self.parentdata = c.call('pool.dataset.query', [['name', '=', fs]], {'get': True})
        super(ZFSDatasetCreateForm, self).__init__(*args, fs=fs, **kwargs)

    def save(self):
        data = {}
        for old, new, save in DATASET_IMMUTABLE_MAPPING + DATASET_COMMON_MAPPING:
            v = (save or (lambda x: x))(self.cleaned_data[old])
            if v != 'INHERIT':
                data[new] = v

        try:
            with client as c:
                c.call('pool.dataset.create', dict(
                    data, name=f"{self.parentdata['name']}/{self.cleaned_data['dataset_name']}", type="FILESYSTEM"))

            return True
        except ValidationErrors as e:
            m = {new: old for old, new, save in DATASET_IMMUTABLE_MAPPING + DATASET_COMMON_MAPPING}
            for err in e.errors:
                field_name = m.get(err.attribute.split('.', 1)[-1])
                error_message = err.errmsg

                if field_name not in self.fields:
                    field_name = '__all__'

                if field_name not in self._errors:
                    self._errors[field_name] = self.error_class([error_message])
                else:
                    self._errors[field_name] += [error_message]

            return False


class ZFSDatasetEditForm(ZFSDatasetCommonForm):

    def __init__(self, *args, fs=None, **kwargs):
        with client as c:
            zdata = c.call('pool.dataset.query', [['name', '=', fs]], {'get': True})
            self.parentdata = c.call('pool.dataset.query', [['name', '=', fs.rsplit('/', 1)[0]]], {'get': True})

        super(ZFSDatasetEditForm, self).__init__(*args, fs=fs, **kwargs)

        if 'comments' in zdata and zdata['comments']['source'] == 'LOCAL':
            self.fields['dataset_comments'].initial = zdata['comments']['value']

        for k, v in self.get_initial_data(zdata).items():
            self.fields[k].initial = v

    @classmethod
    def get_initial_data(cls, zdata):
        """
        Method to get initial data for the form.
        This is a separate method to share with API code.
        """
        data = {}

        for prop in ['quota', 'refquota', 'reservation', 'refreservation']:
            field_name = f'dataset_{prop}'
            if zdata[prop]['value'] == '0' or zdata[prop]['value'] == 'none':
                data[field_name] = 0
            else:
                if zdata[prop]['source'] == 'LOCAL':
                    data[field_name] = zdata[prop]['value']

        if zdata['deduplication']['source'] in ['DEFAULT', 'INHERITED']:
            data['dataset_dedup'] = 'inherit'
        elif zdata['deduplication']['value'] in ('ON', 'OFF', 'VERIFY'):
            data['dataset_dedup'] = zdata['deduplication']['value'].lower()
        elif zdata['deduplication']['value'] == 'SHA256,VERIFY':
            data['dataset_dedup'] = 'verify'
        else:
            data['dataset_dedup'] = 'off'

        if zdata['sync']['source'] in ['DEFAULT', 'INHERITED']:
            data['dataset_sync'] = 'inherit'
        else:
            data['dataset_sync'] = zdata['sync']['value'].lower()

        if zdata['compression']['source'] in ['DEFAULT', 'INHERITED']:
            data['dataset_compression'] = 'inherit'
        else:
            data['dataset_compression'] = zdata['compression']['value'].lower()

        if zdata['atime']['source'] in ['DEFAULT', 'INHERITED']:
            data['dataset_atime'] = 'inherit'
        elif zdata['atime']['value'] in ('ON', 'OFF'):
            data['dataset_atime'] = zdata['atime']['value'].lower()
        else:
            data['dataset_atime'] = 'off'

        if zdata['readonly']['source'] in ['DEFAULT', 'INHERITED']:
            data['dataset_readonly'] = 'inherit'
        elif zdata['readonly']['value'] in ('ON', 'OFF'):
            data['dataset_readonly'] = zdata['readonly']['value'].lower()
        else:
            data['dataset_readonly'] = 'off'

        if zdata['exec']['source'] in ['DEFAULT', 'INHERITED']:
            data['dataset_exec'] = 'inherit'
        elif zdata['exec']['value'] in ('ON', 'OFF'):
            data['dataset_exec'] = zdata['exec']['value'].lower()
        else:
            data['dataset_exec'] = 'off'

        if zdata['recordsize']['source'] in ['DEFAULT', 'INHERITED']:
            data['dataset_recordsize'] = 'inherit'
        else:
            data['dataset_recordsize'] = zdata['recordsize']['value']

        data['dataset_share_type'] = zdata['share_type'].lower()

        for k in ['quota_warning', 'quota_critical', 'refquota_warning', 'refquota_critical']:
            if k in zdata and zdata[k]['source'] == 'LOCAL':
                try:
                    data[k] = int(zdata[k]['value'])
                except ValueError:
                    pass

        return data

    def save(self):
        data = {}
        for old, new, save in DATASET_COMMON_MAPPING:
            v = (save or (lambda x: x))(self.cleaned_data[old])
            data[new] = v

        try:
            with client as c:
                c.call('pool.dataset.update', self._fs, data)

            return True
        except ValidationErrors as e:
            m = {new: old for old, new, save in DATASET_COMMON_MAPPING}
            for err in e.errors:
                field_name = m.get(err.attribute.split('.', 1)[-1])
                error_message = err.errmsg

                if field_name not in self.fields:
                    field_name = '__all__'

                if field_name not in self._errors:
                    self._errors[field_name] = self.error_class([error_message])
                else:
                    self._errors[field_name] += [error_message]

            return False


class CommonZVol(Form):
    zvol_comments = forms.CharField(max_length=120, label=_('Comments'), required=False)
    zvol_volsize = SizeField(
        label=_('Size for this zvol'),
        help_text=_('Example: 1 GiB'),
    )
    zvol_force = forms.BooleanField(
        label=_('Force size'),
        required=False,
        help_text=_('Allow the zvol to consume more than 80% of available space'),
    )
    zvol_sync = forms.ChoiceField(
        choices=choices.ZFS_SyncChoices,
        initial='inherit',
        widget=forms.Select(attrs=attrs_dict),
        label=_('Sync'))
    zvol_compression = forms.ChoiceField(
        choices=choices.ZFS_CompressionChoices,
        initial='inherit',
        widget=forms.Select(attrs=attrs_dict),
        label=_('Compression level'))
    zvol_dedup = forms.ChoiceField(
        label=_('ZFS Deduplication'),
        choices=choices.ZFS_DEDUP_INHERIT,
        initial='inherit',
        widget=WarningSelect(text=DEDUP_WARNING),
    )

    def __init__(self, *args, **kwargs):
        self._force = False
        super(CommonZVol, self).__init__(*args, **kwargs)

        if hasattr(self, 'parentdata'):
            self.fields['zvol_sync'].choices = _inherit_choices(
                choices.ZFS_SyncChoices,
                self.parentdata['sync']['value'].lower()
            )
            self.fields['zvol_compression'].choices = _inherit_choices(
                choices.ZFS_CompressionChoices,
                self.parentdata['compression']['value'].lower()
            )
            self.fields['zvol_dedup'].choices = _inherit_choices(
                choices.ZFS_DEDUP_INHERIT,
                self.parentdata['deduplication']['value'].lower()
            )

        if not dedup_enabled():
            self.fields['zvol_dedup'].widget.attrs['readonly'] = True
            self.fields['zvol_dedup'].widget.attrs['class'] = (
                'dijitSelectDisabled dijitDisabled')
            self.fields['zvol_dedup'].widget.text = mark_safe(
                '<span style="color: red;">Dedup feature not activated. '
                'Contact <a href="mailto:truenas-support@ixsystems.com?subject'
                '=ZFS Deduplication Activation">TrueNAS Support</a> for '
                'assistance.</span><br />'
            )


ZVOL_COMMON_MAPPING = [
    ('zvol_comments', 'comments', None),
    ('zvol_sync', 'sync', str.upper),
    ('zvol_compression', 'compression', str.upper),
    ('zvol_dedup', 'deduplication', str.upper),
    ('zvol_volsize', 'volsize', None),
    ('zvol_force', 'force_size', None),
]


class ZVol_EditForm(CommonZVol):

    def __init__(self, *args, **kwargs):
        # parentds is required for CommonZVol
        self.name = kwargs.pop('name')
        self.parentds = self.name.rsplit('/', 1)[0]
        with client as c:
            self.zdata = c.call('pool.dataset.query', [['name', '=', self.name]], {'get': True})
            self.parentdata = c.call('pool.dataset.query', [['name', '=', self.parentds]], {'get': True})
        super(ZVol_EditForm, self).__init__(*args, **kwargs)

        if self.zdata['comments']['source'] == 'LOCAL':
            self.fields['zvol_comments'].initial = self.zdata['comments']['value']
        if self.zdata['sync']['source'] in ['DEFAULT', 'INHERITED']:
            self.fields['zvol_sync'].initial = 'inherit'
        else:
            self.fields['zvol_sync'].initial = self.zdata['sync']['value'].lower()
        if self.zdata['compression']['source'] in ['DEFAULT', 'INHERITED']:
            self.fields['zvol_compression'].initial = 'inherit'
        else:
            self.fields['zvol_compression'].initial = self.zdata['compression']['value'].lower()
        self.fields['zvol_volsize'].initial = self.zdata['volsize']['parsed']

        if self.zdata['deduplication']['source'] in ['DEFAULT', 'INHERITED']:
            self.fields['zvol_dedup'].initial = 'inherit'
        elif self.zdata['deduplication']['value'] in ('ON', 'OFF', 'VERIFY'):
            self.fields['zvol_dedup'].initial = self.zdata['deduplication']['value'].lower()
        elif self.zdata['deduplication']['value'] == 'SHA256,VERIFY':
            self.fields['zvol_dedup'].initial = 'verify'
        else:
            self.fields['zvol_dedup'].initial = 'off'

        if not dedup_enabled():
            self.fields['zvol_dedup'].widget.attrs['readonly'] = True
            self.fields['zvol_dedup'].widget.attrs['class'] = (
                'dijitSelectDisabled dijitDisabled')
            self.fields['zvol_dedup'].widget.text = mark_safe(
                '<span style="color: red;">Dedup feature not activated. '
                'Contact <a href="mailto:truenas-support@ixsystems.com?subject'
                '=ZFS Deduplication Activation">TrueNAS Support</a> for '
                'assistance.</span><br />'
            )

    def save(self):
        data = {}
        for old, new, save in ZVOL_COMMON_MAPPING:
            data[new] = (save or (lambda x: x))(self.cleaned_data[old])

        if data['volsize'] == self.zdata['volsize']['parsed']:
            data.pop('volsize')

        try:
            with client as c:
                c.call('pool.dataset.update', self.name, data)

            return True
        except ClientException as e:
            field_name = '__all__'
            error_message = e.error

            if field_name not in self._errors:
                self._errors[field_name] = self.error_class([error_message])
            else:
                self._errors[field_name] += [error_message]
        except ValidationErrors as e:
            m = {new: old for old, new, save in ZVOL_COMMON_MAPPING}
            for err in e.errors:
                field_name = m.get(err.attribute.split('.', 1)[-1])
                error_message = err.errmsg

                if field_name not in self.fields:
                    field_name = '__all__'

                if field_name not in self._errors:
                    self._errors[field_name] = self.error_class([error_message])
                else:
                    self._errors[field_name] += [error_message]

            return False


ZVOL_IMMUTABLE_MAPPING = [
    ('zvol_name', 'name', None),
    ('zvol_sparse', 'sparse', None),
    ('zvol_blocksize', 'volblocksize', str.upper),
]


class ZVol_CreateForm(CommonZVol):
    zvol_name = forms.CharField(max_length=128, label=_('zvol name'))
    zvol_sparse = forms.BooleanField(
        label=_('Sparse volume'),
        help_text=_(
            'Creates a sparse volume with no reservation, also known '
            'as "thin provisioning". A "sparse volume" is a volume where the '
            'reservation is less than the volume size. Consequently, writes '
            'to a sparse volume can fail with ENOSPC when the pool is low on '
            'space. (NOT RECOMMENDED)'),
        required=False,
        initial=False,
    )
    zvol_blocksize = forms.ChoiceField(
        label=_('Block size'),
        help_text=_(
            'The default of the zvol block size is chosen automatically based '
            'on the number of the disks in the pool for a general use case.'
        ),
        required=False,
        choices=(('INHERIT', _('Inherit')), ) + choices.ZFS_VOLBLOCKSIZE,
        initial='INHERIT',
    )

    advanced_fields = (
        'zvol_blocksize',
    )

    def __init__(self, *args, **kwargs):
        self.parentds = kwargs.pop('parentds')
        with client as c:
            self.parentdata = c.call('pool.dataset.query', [['name', '=', self.parentds]], {'get': True})
            size = c.call('pool.dataset.recommended_zvol_blocksize', self.parentds)
        super(ZVol_CreateForm, self).__init__(*args, **kwargs)
        key_order(self, 0, 'zvol_name', instance=True)

        if size in [y[0] for y in choices.ZFS_VOLBLOCKSIZE]:
            self.fields['zvol_blocksize'].initial = size

    def save(self):
        data = {}
        for old, new, save in ZVOL_IMMUTABLE_MAPPING + ZVOL_COMMON_MAPPING:
            v = (save or (lambda x: x))(self.cleaned_data[old])
            if v != 'INHERIT':
                data[new] = v

        try:
            with client as c:
                c.call('pool.dataset.create', dict(data, name=f"{self.parentds}/{self.cleaned_data['zvol_name']}",
                                                   type="VOLUME"))

            return True
        except ValidationErrors as e:
            m = {new: old for old, new, save in ZVOL_IMMUTABLE_MAPPING + ZVOL_COMMON_MAPPING}
            for err in e.errors:
                field_name = m.get(err.attribute.split('.', 1)[-1])
                error_message = err.errmsg

                if field_name not in self.fields:
                    field_name = '__all__'

                if field_name not in self._errors:
                    self._errors[field_name] = self.error_class([error_message])
                else:
                    self._errors[field_name] += [error_message]

            return False


class MountPointAccessForm(Form):
    mp_user_en = forms.BooleanField(
        label=_('Apply Owner (user)'),
        initial=True,
        required=False,
    )
    mp_user = UserField(label=_('Owner (user)'))
    mp_group_en = forms.BooleanField(
        label=_('Apply Owner (group)'),
        initial=True,
        required=False,
    )
    mp_group = GroupField(label=_('Owner (group)'))
    mp_mode_en = forms.BooleanField(
        label=_('Apply Mode'),
        initial=True,
        required=False,
    )
    mp_mode = UnixPermissionField(label=_('Mode'), required=False)
    mp_acl = forms.ChoiceField(
        label=_('Permission Type'),
        choices=(
            ('unix', 'Unix'),
            ('mac', 'Mac'),
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
            with client as c:
                stat = c.call('filesystem.stat', path)

                self.fields['mp_acl'].initial = stat['acl']

                if stat['acl'] == 'windows':
                    self.fields['mp_mode'].widget.attrs['disabled'] = 'disabled'

                self.fields['mp_mode'].initial = "%.3o" % stat['mode']
                self.fields['mp_user'].initial = stat['user']
                self.fields['mp_group'].initial = stat['group']

        self.fields['mp_acl'].widget.attrs['onChange'] = "mpAclChange(this);"

    def commit(self, path):

        with client as c:
            dataset = c.call('pool.dataset.query', [['mountpoint', '=', path.rstrip('/')]], {'get': True})

        kwargs = {}

        if self.cleaned_data.get('mp_group_en'):
            kwargs['group'] = self.cleaned_data['mp_group']

        if self.cleaned_data.get('mp_mode_en'):
            kwargs['mode'] = str(self.cleaned_data['mp_mode'])

        if self.cleaned_data.get('mp_user_en'):
            kwargs['user'] = self.cleaned_data['mp_user']

        kwargs['acl'] = self.cleaned_data['mp_acl'].upper()

        kwargs['recursive'] = self.cleaned_data['mp_recursive']

        with client as c:
            try:
                c.call('pool.dataset.permission', dataset['id'], kwargs)
                return True
            except ValidationErrors as e:
                for err in e.errors:
                    field_name = 'mp_' + err.attribute.split('.', 1)[-1]
                    error_message = err.errmsg

                    if field_name not in self.fields:
                        field_name = '__all__'

                    if field_name not in self._errors:
                        self._errors[field_name] = self.error_class([error_message])
                    else:
                        self._errors[field_name] += [error_message]

                return False


class ResilverForm(MiddlewareModelForm, ModelForm):

    middleware_attr_schema = 'pool_resilver'
    middleware_attr_prefix = ''
    middleware_plugin = 'pool.resilver'
    is_singletone = True

    class Meta:
        fields = '__all__'
        model = models.Resilver
        widgets = {
            'weekday': CheckboxSelectMultiple(
                choices=choices.WEEKDAYS_CHOICES
            ),
        }

    def __init__(self, *args, **kwargs):
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            fix_time_fields(new, ['begin', 'end'])
            args = (new,) + args[1:]
        super(ResilverForm, self).__init__(*args, **kwargs)

    def clean_weekday(self):
        return self.data.getlist('weekday')

    def clean_begin(self):
        begin = self.data.get('begin')
        return begin.strftime('%H:%M')

    def clean_end(self):
        end = self.data.get('end')
        return end.strftime('%H:%M')


class PeriodicSnapForm(MiddlewareModelForm, ModelForm):

    middleware_attr_schema = 'periodic_snapshot'
    middleware_attr_prefix = 'task_'
    middleware_plugin = 'pool.snapshottask'
    middleware_attr_map = {
        'dow': 'task_byweekday'
    }
    is_singletone = False

    class Meta:
        fields = '__all__'
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
            fix_time_fields(new, ['task_begin', 'task_end'])
            args = (new,) + args[1:]
        super(PeriodicSnapForm, self).__init__(*args, **kwargs)
        self.fields['task_filesystem'] = forms.ChoiceField(
            label=self.fields['task_filesystem'].label,
        )
        filesystem_choices = sorted(list(choices.FILESYSTEM_CHOICES()))
        if self.instance.id and self.instance.task_filesystem not in dict(filesystem_choices):
            filesystem_choices.append((self.instance.task_filesystem, self.instance.task_filesystem))
        self.fields['task_filesystem'].choices = filesystem_choices
        self.fields['task_repeat_unit'].widget = forms.HiddenInput()

    def clean_task_begin(self):
        begin = self.cleaned_data.get('task_begin')
        return begin.strftime('%H:%M')

    def clean_task_end(self):
        end = self.cleaned_data.get('task_end')
        return end.strftime('%H:%M')

    def clean_task_byweekday(self):
        bwd = self.data.getlist('task_byweekday')
        return bwd

    def middleware_clean(self, data):
        data['dow'] = [int(day) for day in data.pop('byweekday')]
        data.pop('repeat_unit', None)
        data['ret_unit'] = data['ret_unit'].upper()
        return data


class ManualSnapshotForm(Form):
    ms_recursively = forms.BooleanField(
        initial=False,
        required=False,
        label=_('Recursive snapshot'))

    ms_name = forms.CharField(label=_('Snapshot Name'))

    vmwaresync = forms.BooleanField(
        required=False,
        label=_('VMware Sync'),
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        self._fs = kwargs.pop('fs', None)
        super(ManualSnapshotForm, self).__init__(*args, **kwargs)
        self.fields['ms_name'].initial = datetime.today().strftime(
            'manual-%Y%m%d')
        if not models.VMWarePlugin.objects.filter(filesystem=self._fs).exists():
            self.fields.pop('vmwaresync')

    def clean_ms_name(self):
        regex = re.compile('^[-a-zA-Z0-9_. ]+$')
        name = self.cleaned_data.get('ms_name')
        if regex.match(name) is None:
            raise forms.ValidationError(
                _("Only [-a-zA-Z0-9_. ] permitted as snapshot name")
            )
        snaps = notifier().zfs_snapshot_list(path=f'{self._fs}@{name}')
        if snaps:
            raise forms.ValidationError(
                _('Snapshot with this name already exists')
            )
        return name

    def commit(self, fs):
        vmsnapname = str(uuid.uuid4())
        vmsnapdescription = str(datetime.now()).split('.')[0] + " FreeNAS Created Snapshot"
        snapvms = []
        if self.cleaned_data.get('vmwaresync'):
            for obj in models.VMWarePlugin.objects.filter(filesystem=self._fs):
                try:
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
                    ssl_context.verify_mode = ssl.CERT_NONE

                    si = connect.SmartConnect(host=obj.hostname, user=obj.username, pwd=obj.get_password(), sslContext=ssl_context)
                except Exception:
                    continue
                content = si.RetrieveContent()
                vm_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
                for vm in vm_view.view:
                    if vm.summary.runtime.powerState != 'poweredOn':
                        continue
                    for i in vm.datastore:
                        if i.info.name == obj.datastore:
                            VimTask.WaitForTask(vm.CreateSnapshot_Task(
                                name=vmsnapname,
                                description=vmsnapdescription,
                                memory=False, quiesce=False,
                            ))
                            snapvms.append(vm)
                            break
        try:
            notifier().zfs_mksnap(
                fs,
                str(self.cleaned_data['ms_name']),
                self.cleaned_data['ms_recursively'],
                len(snapvms))
        finally:
            for vm in snapvms:
                tree = vm.snapshot.rootSnapshotList
                while tree[0].childSnapshotList is not None:
                    snap = tree[0]
                    if snap.name == vmsnapname:
                        VimTask.WaitForTask(snap.snapshot.RemoveSnapshot_Task(True))
                    if len(tree[0].childSnapshotList) < 1:
                        break
                    tree = tree[0].childSnapshotList


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
            if '/' in dataset:
                dataset = '%s-' % dataset
            else:
                dataset = '%s/' % dataset
            self.fields['cs_name'].initial = '%s%s-clone' % (
                dataset,
                snapname)

    def clean_cs_snapshot(self):
        return self.fields['cs_snapshot'].initial

    def clean_cs_name(self):
        regex = re.compile('^[-a-zA-Z0-9_./ ]+$')
        if regex.match(self.cleaned_data['cs_name'].__str__()) is None:
            raise forms.ValidationError(
                _("Only [-a-zA-Z0-9_./ ] permitted as clone name")
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


class ZFSDiskReplacementForm(Form):

    force = forms.BooleanField(
        label=_("Force"),
        required=False,
    )
    replace_disk = forms.ChoiceField(
        choices=(),
        widget=forms.Select(attrs=attrs_dict),
        label=_('Member disk'))

    def __init__(self, *args, **kwargs):
        self.volume = kwargs.pop('volume')
        self.label = kwargs.pop('label')
        disk = notifier().label_to_disk(self.label)
        if disk is None:
            disk = self.label
        self.disk = disk
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
        self.fields['replace_disk'].choices = self._populate_disk_choices()

    def _populate_disk_choices(self):
        diskchoices = []
        with client as c:
            unused_disks = c.call('disk.get_unused')

        for disk in unused_disks:
            if disk['size']:
                capacity = humanize_number_si(disk['size'])
                label = f'{disk["devname"]} ({capacity})'
            else:
                label = disk['devname']
            diskchoices.append((disk['devname'], label))
        return diskchoices

    def clean_pass2(self):
        passphrase = self.cleaned_data.get("pass")
        passphrase2 = self.cleaned_data.get("pass2")
        if passphrase != passphrase2:
            raise forms.ValidationError(
                _("Confirmation does not match passphrase")
            )
        return passphrase

    def done(self):
        devname = self.cleaned_data['replace_disk']
        passphrase = self.cleaned_data.get("pass")

        replace_args = {}
        if passphrase:
            replace_args['passphrase'] = passphrase

        with client as c:
            identifier = c.call('disk.query', [('devname', '=', devname)])[0]['identifier']
            try:
                c.call('pool.replace', self.volume.id, dict({
                    'label': self.label,
                    'disk': identifier,
                    'force': self.cleaned_data.get('force'),
                }, **replace_args), job=True)
            except ValidationErrors as e:
                self._errors['__all__'] = self.error_class([err.errmsg for err in e.errors])
                return False
        return True


class ReplicationForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = "repl_"
    middleware_attr_schema = "replication"
    middleware_plugin = "replication"
    is_singletone = False

    repl_remote_mode = forms.ChoiceField(
        label=_('Setup mode'),
        choices=(
            ('MANUAL', _('Manual')),
            ('SEMIAUTOMATIC', _('Semi-automatic')),
        ),
        initial='MANUAL',
    )
    repl_remote_hostname = forms.CharField(label=_("Remote hostname"))
    repl_remote_port = forms.IntegerField(
        label=_("Remote port"),
        initial=22,
        required=False,
        widget=forms.widgets.TextInput(),
    )
    repl_remote_http_port = forms.CharField(
        label=_('Remote HTTP/HTTPS Port'),
        max_length=200,
        initial=80,
        required=False,
    )
    repl_remote_https = forms.BooleanField(
        label=_('Remote HTTPS'),
        required=False,
        initial=False,
    )
    repl_remote_token = forms.CharField(
        label=_('Remote Auth Token'),
        max_length=100,
        required=False,
        help_text=_(
            "On the remote host go to Storage -> Replication Tasks, click the "
            "Temporary Auth Token button and paste the resulting value in to "
            "this field."
        ),
    )
    repl_remote_dedicateduser_enabled = forms.BooleanField(
        label=_("Dedicated User Enabled"),
        help_text=_("If disabled then root will be used for replication."),
        required=False,
    )
    repl_remote_dedicateduser = UserField(
        label=_("Dedicated User"),
        required=False,
    )
    repl_remote_cipher = forms.ChoiceField(
        label=_("Encryption Cipher"),
        initial='standard',
        choices=choices.REPL_CIPHER,
    )
    repl_remote_hostkey = forms.CharField(
        label=_("Remote hostkey"),
        widget=forms.Textarea(),
        required=False,
    )

    class Meta:
        fields = '__all__'
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
            fix_time_fields(new, ['repl_begin', 'repl_end'])
            args = (new,) + args[1:]
        repl = kwargs.get('instance', None)
        super(ReplicationForm, self).__init__(*args, **kwargs)
        self.fields['repl_filesystem'] = forms.ChoiceField(
            label=self.fields['repl_filesystem'].label,
            help_text=_(
                "This field will be empty if you have not "
                "setup a periodic snapshot task"),
        )
        fs = sorted(list(set([
            (task.task_filesystem, task.task_filesystem)
            for task in models.Task.objects.all()
        ])))
        self.fields['repl_filesystem'].choices = fs

        if not self.instance.id:
            self.fields['repl_remote_mode'].widget.attrs['onChange'] = (
                'repliRemoteMode'
            )
        else:
            del self.fields['repl_remote_mode']
            del self.fields['repl_remote_http_port']
            del self.fields['repl_remote_https']
            del self.fields['repl_remote_token']

        self.fields['repl_remote_dedicateduser_enabled'].widget.attrs[
            'onClick'
        ] = (
            'toggleGeneric("id_repl_remote_dedicateduser_enabled", '
            '["id_repl_remote_dedicateduser"], true);')

        self.fields['repl_remote_cipher'].widget.attrs['onChange'] = (
            'remoteCipherConfirm'
        )

        if repl and repl.id:
            self.fields['repl_remote_hostname'].initial = (
                repl.repl_remote.ssh_remote_hostname)
            self.fields['repl_remote_hostname'].required = False
            self.fields['repl_remote_port'].initial = (
                repl.repl_remote.ssh_remote_port)
            self.fields['repl_remote_dedicateduser_enabled'].initial = (
                repl.repl_remote.ssh_remote_dedicateduser_enabled)
            self.fields['repl_remote_dedicateduser'].initial = (
                repl.repl_remote.ssh_remote_dedicateduser)
            self.fields['repl_remote_cipher'].initial = (
                repl.repl_remote.ssh_cipher)
            self.fields['repl_remote_hostkey'].initial = (
                repl.repl_remote.ssh_remote_hostkey)
            self.fields['repl_remote_hostkey'].required = False
            if not repl.repl_remote.ssh_remote_dedicateduser_enabled:
                self.fields['repl_remote_dedicateduser'].widget.attrs[
                    'disabled'] = 'disabled'
        else:
            if not self.data.get("repl_remote_dedicateduser_enabled", False):
                self.fields['repl_remote_dedicateduser'].widget.attrs[
                    'disabled'] = 'disabled'

        self.fields['repl_remote_cipher'].widget.attrs['data-dojo-props'] = (
            mark_safe("'oldvalue': '%s'" % (
                self.fields['repl_remote_cipher'].initial,
            ))
        )

    def clean_repl_remote_port(self):
        port = self.cleaned_data.get('repl_remote_port')
        if not port:
            return 22
        return port

    def clean_repl_remote_http_port(self):
        port = self.cleaned_data.get('repl_remote_http_port')
        mode = self.cleaned_data.get('repl_remote_mode')
        if mode == 'SEMIAUTOMATIC' and not port:
            return 80
        return port

    def clean_repl_begin(self):
        return self.cleaned_data.get('repl_begin').strftime('%H:%M')

    def clean_repl_end(self):
        return self.cleaned_data.get('repl_end').strftime('%H:%M')

    def middleware_clean(self, data):

        data['compression'] = data['compression'].upper()
        data['remote_cipher'] = data['remote_cipher'].upper()
        remote_http_port = int(data.pop('remote_http_port', 80))
        remote_port = int(data.pop('remote_port', 22))

        mode = data.get('remote_mode', 'MANUAL')
        if mode == 'SEMIAUTOMATIC':
            data['remote_port'] = remote_http_port
        else:
            data['remote_port'] = remote_port

        return data


class ReplRemoteForm(ModelForm):

    class Meta:
        fields = '__all__'
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
        if list(services.keys()):
            self.fields['cascade'] = forms.BooleanField(
                initial=True,
                required=False,
                label=_("Also delete the share's configuration"))

    def done(self, request, events, **kwargs):
        cascade = self.cleaned_data.get('cascade')
        if cascade is None:
            cascade = True
        with client as c:
            c.call('pool.export', self.instance.id, {
                'cascade': cascade,
                'destroy': self.cleaned_data.get('mark_new'),
            }, job=True)
        super().done(request, events, **kwargs)


class Dataset_Destroy(Form):
    def __init__(self, *args, **kwargs):
        self.fs = kwargs.pop('fs')
        self.datasets = kwargs.pop('datasets', [])
        super(Dataset_Destroy, self).__init__(*args, **kwargs)
        with client as c:
            snaps = c.call("zfs.snapshot.query", [["dataset", "=", self.fs]])
        if len(snaps) > 0:
            label = ungettext(
                "I'm aware this will destroy snapshots within this dataset",
                ("I'm aware this will destroy all child datasets and "
                    "snapshots within this dataset"),
                len(self.datasets)
            )
            self.fields['cascade'] = forms.BooleanField(
                initial=False,
                label=label)


class ZvolDestroyForm(Form):
    def __init__(self, *args, **kwargs):
        self.fs = kwargs.pop('fs')
        super(ZvolDestroyForm, self).__init__(*args, **kwargs)
        snaps = notifier().zfs_snapshot_list(path=self.fs)
        if len(snaps.get(self.fs, [])) > 0:
            label = _(
                "I'm aware this will destroy snapshots of this zvol",
            )
            self.fields['cascade'] = forms.BooleanField(
                initial=False,
                label=label)


class ScrubForm(MiddlewareModelForm, ModelForm):

    middleware_attr_prefix = 'scrub_'
    middleware_attr_schema = 'pool_scrub'
    middleware_plugin = 'pool.scrub'
    is_singletone = False
    middleware_attr_map = {
        'pool': 'scrub_volume'
    }

    class Meta:
        fields = '__all__'
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
        m = self.data.getlist('scrub_month')
        if len(m) == 12:
            return '*'
        else:
            return ','.join(m)

    def clean_scrub_dayweek(self):
        w = self.data.getlist('scrub_dayweek')
        if len(w) == 7:
            return '*'
        else:
            return ','.join(w)

    def middleware_clean(self, update):
        update['pool'] = update.pop('volume')
        update['schedule'] = {
            'minute': update.pop('minute'),
            'hour': update.pop('hour'),
            'dom': update.pop('daymonth'),
            'month': update.pop('month'),
            'dow': update.pop('dayweek')
        }
        return update


class DiskWipeForm(Form):

    method = forms.ChoiceField(
        label=_("Method"),
        choices=(
            ("QUICK", _("Quick")),
            ("FULL", _("Full with zeros")),
            ("FULL_RANDOM", _("Full with random data")),
        ),
        widget=forms.widgets.RadioSelect(),
    )

    def __init__(self, *args, **kwargs):
        self.disk = kwargs.pop('disk')
        super().__init__(*args, **kwargs)

    def clean(self):
        with client as c:
            if self.disk in c.call('disk.get_reserved'):
                self._errors['__all__'] = self.error_class([
                    _('The disk %s is currently in use and cannot be wiped.') % self.disk
                ])
        return self.cleaned_data


class CreatePassphraseForm(Form):

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
        with client as c:
            return c.call('pool.passphrase', volume.id, {'passphrase': passphrase})


class ChangePassphraseForm(Form):

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
            self._errors.pop('passphrase', None)
            self._errors.pop('passphrase2', None)
        return cdata

    def done(self, volume):
        if self.cleaned_data.get("remove"):
            passphrase = None
        else:
            passphrase = self.cleaned_data.get("passphrase")

        try:
            with client as c:
                return c.call('pool.passphrase', volume.id, {
                    'admin_password': self.cleaned_data.get('adminpw'),
                    'passphrase': passphrase,
                })
        except ValidationErrors as e:
            for err in e.errors:
                if err.attribute == 'options.admin_password':
                    field = 'adminpw'
                elif err.attribute == 'options.passphrase':
                    field = 'passphrase'
                else:
                    field = '__all__'
                if field not in self._errors:
                    self._errors[field] = self.error_class()
                self._errors[field].append(err.errmsg)
            return False


class UnlockPassphraseForm(Form):

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
        initial=['afp', 'cifs', 'ftp', 'iscsitarget', 'jails', 'nfs', 'webdav'],
        required=False,
    )
    recovery_key = forms.CharField(  # added for api v1 support
        required=False,
        widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super(UnlockPassphraseForm, self).__init__(*args, **kwargs)
        with client as c:
            self.fields['services'].choices = list(
                c.call('pool.unlock_services_restart_choices').items()
            )

    def clean(self):
        passphrase = self.cleaned_data.get("passphrase")
        key = self.cleaned_data.get("key")
        recovery_key = self.cleaned_data.get('recovery_key')
        if not passphrase and key is None and not recovery_key:
            self._errors['__all__'] = self.error_class([
                _("You need either a passphrase or a recovery key to unlock")
            ])
        return self.cleaned_data

    def done(self, volume):
        passphrase = self.cleaned_data.get("passphrase")
        key = self.cleaned_data.get("key") or self.cleaned_data.get('recovery_key')

        if passphrase:
            with client as c:
                c.call('pool.unlock', volume.id, {
                    'passphrase': passphrase,
                    'services_restart': self.cleaned_data.get('services'),
                }, job=True)
        elif key is not None:
            keyfile = tempfile.mktemp(dir='/tmp/')
            with open(keyfile, 'wb+') as f:
                os.chmod(keyfile, 600)
                f.write(key.read() if not isinstance(key, str) else base64.b64decode(key))
                f.flush()
                f.seek(0)
                upload_job_and_wait(f, 'pool.unlock', volume.id, {
                    'recoverykey': True,
                    'services_restart': self.cleaned_data.get('services'),
                })
            os.unlink(keyfile)
        else:
            raise ValueError("Need a passphrase or recovery key")

        """
        if not _notifier.is_freenas() and _notifier.failover_licensed():
            from freenasUI.failover.enc_helper import LocalEscrowCtl
            escrowctl = LocalEscrowCtl()
            escrowctl.setkey(passphrase)
            try:
                with client as c:
                    c.call('failover.call_remote', 'failover.encryption_setkey', [passphrase])
            except Exception:
                log.warn('Failed to set key on standby node, is it down?', exc_info=True)
            if _notifier.failover_status() != 'MASTER':
                _notifier.failover_force_master()
        """


class KeyForm(Form):

    adminpw = forms.CharField(
        label=_("Root password"),
        widget=forms.widgets.PasswordInput(),
    )

    def __init__(self, *args, **kwargs):
        super(KeyForm, self).__init__(*args, **kwargs)

        if self._api is True:
            del self.fields['adminpw']

    def clean_adminpw(self):
        pw = self.cleaned_data.get("adminpw")
        valid = False
        for user in bsdUsers.objects.filter(bsdusr_uid=0):
            if user.check_password(pw):
                valid = True
                break
        if valid is False:
            raise forms.ValidationError(
                _("Invalid password")
            )
        return pw


class ReKeyForm(KeyForm):

    def __init__(self, *args, **kwargs):
        self.volume = kwargs.pop('volume')
        super(ReKeyForm, self).__init__(*args, **kwargs)

    def done(self):
        options = {}
        adminpw = self.cleaned_data.get('adminpw')
        if adminpw is not None:
            options['admin_password'] = adminpw
        try:
            with client as c:
                return c.call('pool.rekey', self.volume.id, options)
        except ClientException as e:
            self._errors['__all__'] = self.error_class([str(e)])
            return False


class VMWarePluginForm(MiddlewareModelForm, ModelForm):

    middleware_attr_schema = 'vmware'
    middleware_attr_prefix = ''
    middleware_plugin = 'vmware'
    is_singletone = False

    oid = forms.CharField(
        widget=forms.widgets.HiddenInput,
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.VMWarePlugin
        widgets = {
            'password': forms.widgets.PasswordInput(),
            'datastore': forms.widgets.ComboBox(),
        }

    def __init__(self, *args, **kwargs):
        super(VMWarePluginForm, self).__init__(*args, **kwargs)
        self.fields['password'].required = False
        self.fields['password'].widget.attrs['onchange'] = (
            "vmwareDatastores('%s', dijit.byId('id_datastore'))" % (
                reverse('storage_vmwareplugin_datastores')
            )
        )
        self.fields['filesystem'] = forms.ChoiceField(
            label=self.fields['filesystem'].label,
        )
        self.fields['filesystem'].choices = sorted(choices.FILESYSTEM_CHOICES())
        if self.instance.id:
            self.fields['oid'].initial = self.instance.id

    def middleware_clean(self, data):
        data.pop('oid', None)
        return data
