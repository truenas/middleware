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
import re
from datetime import datetime, time
from os import popen

from django.http import QueryDict
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as __
from django.core.urlresolvers import reverse
from django.db import transaction

from freenasUI.middleware.notifier import notifier
from freenasUI.common.forms import ModelForm, Form
from freenasUI.common import humanize_size, humanize_number_si
from freenasUI.storage import models
from freenasUI import choices
from freenasUI.common.freenasldap import FreeNAS_Users, FreeNAS_Groups, \
                                         FreeNAS_User, FreeNAS_Group
from freeadmin.forms import UserField, GroupField
from dojango.forms import widgets, CheckboxSelectMultiple
from dojango import forms

attrs_dict = { 'class': 'required', 'maxHeight': 200 }

class UnixPermissionWidget(widgets.MultiWidget):

    def __init__(self, attrs=None):

        widgets = [forms.widgets.CheckboxInput,] * 9
        super(UnixPermissionWidget, self).__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            if isinstance(value, str) or isinstance(value, unicode):
                owner = bin(int(value[0]))[2:]
                group = bin(int(value[1]))[2:]
                other = bin(int(value[2]))[2:]
                # make sure we end up with 9 bits
                mode = "0" * (3-len(owner)) + owner + \
                        "0" * (3-len(group)) + group + \
                        "0" * (3-len(other)) + other

                rv = [False, False, False, False, False, False, False, False, False]
                for i in range(9):
                    if mode[i] == '1':
                        rv[i] = True

                return rv
        return [False, False, False, False, False, False, False, False, False]

    def format_output(self, rendered_widgets):

        maprow = {
                1: __('Read'),
                2: __('Write'),
                3: __('Execute'),
            }

        html = """<table>
        <thead>
        <tr>
        <td></td>
        <td>%s</td>
        <td>%s</td>
        <td>%s</td>
        </tr>
        </thead>
        <tbody>
        """ % ( __('Owner'), __('Group'), __('Other') )
        for i in range(1,4):
            html += "<tr>"
            html += "<td>%s</td>" % maprow[i]
            for j in range(1,4):
                html += "<td>" + rendered_widgets[j*3-3+i-1] + "</td>"
            html += "</tr>"
        html += "</tbody></table>"

        return html

class UnixPermissionField(forms.MultiValueField):

    widget = UnixPermissionWidget()

    def __init__(self, *args, **kwargs):
        fields = [forms.BooleanField()] * 9
        super(UnixPermissionField, self).__init__(fields, *args, **kwargs)

    def compress(self, value):
        if value:
            owner = 0
            group = 0
            other = 0
            if value[0] == True:
                owner += 4
            if value[1] == True:
                owner += 2
            if value[2] == True:
                owner += 1
            if value[3] == True:
                group += 4
            if value[4] == True:
                group += 2
            if value[5] == True:
                group += 1
            if value[6] == True:
                other += 4
            if value[7] == True:
                other += 2
            if value[8] == True:
                other += 1

            return str(owner*100 + group *10 + other)
        return None

class VolumeWizardForm(forms.Form):
    volume_name = forms.CharField(max_length = 30, label = _('Volume name') )
    volume_fstype = forms.ChoiceField(choices = ((x, x) for x in ('UFS', 'ZFS')), widget=forms.RadioSelect(attrs=attrs_dict), label = 'File System type')
    volume_disks = forms.MultipleChoiceField(choices=(), widget=forms.SelectMultiple(attrs=attrs_dict), label = 'Member disks', required=False)
    group_type = forms.ChoiceField(choices=(), widget=forms.RadioSelect(attrs=attrs_dict), required=False)
    force4khack = forms.BooleanField(required=False, initial=False, help_text=_('Force 4096 bytes sector size'))
    def __init__(self, *args, **kwargs):
        super(VolumeWizardForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        self.fields['volume_disks'].choices.sort(key = lambda a : float(re.sub(r'^.*?([0-9]+)[^0-9]*', r'\1.',a[0])))
        self.fields['volume_fstype'].widget.attrs['onClick'] = 'wizardcheckings();'

        grouptype_choices = (
            ('mirror', 'mirror'),
            ('stripe', 'stripe'),
            )
        fstype = self.data.get("volume_fstype", None)
        if self.data.has_key("volume_disks"):
            disks = self.data.getlist("volume_disks")
        else:
            disks = []
        if fstype == "UFS":
            l = len(disks) - 1
            if l >= 2 and (((l-1)&l) == 0):
                grouptype_choices += (
                    ('raid3', 'RAID-3'),
                    )
        elif fstype == "ZFS":
            if len(disks) >= 3:
                grouptype_choices += ( ('raidz', 'RAID-Z'), )
            if len(disks) >= 4:
                grouptype_choices += ( ('raidz2', 'RAID-Z2'), )
            # Not yet
            #if len(disks) >= 5:
            #    grouptype_choices += ( ('raidz3', 'RAID-Z3'), )
        self.fields['group_type'].choices = grouptype_choices

    def _populate_disk_choices(self):

        diskchoices = dict()

        # Grab disk list
        # NOTE: This approach may fail if device nodes are not accessible.
        pipe = popen("/usr/sbin/diskinfo `/sbin/sysctl -n kern.disks | tr ' ' '\n' | grep -v '^cd[0-9]'` | /usr/bin/cut -f1,3")
        diskinfo = pipe.read().strip().split('\n')
        for disk in diskinfo:
            devname, capacity = disk.split('\t')
            capacity = humanize_number_si(capacity)
            diskchoices[devname] = "%s (%s)" % (devname, capacity)
        # Exclude the root device
        rootdev = popen("""glabel status | grep `mount | awk '$3 == "/" {print $1}' | sed -e 's/\/dev\///'` | awk '{print $3}'""").read().strip()
        rootdev_base = re.search('[a-z/]*[0-9]*', rootdev)
        if rootdev_base != None:
            try:
                del diskchoices[rootdev_base.group(0)]
            except:
                pass
        # Exclude what's already added
        for devname in [ notifier().identifier_to_device(x['disk_identifier']) or x['disk_name'] for x in models.Disk.objects.all().values('disk_name','disk_identifier')]:
            diskchoices.pop(devname, None)
        choices = diskchoices.items()
        choices.sort(key = lambda a : float(re.sub(r'^.*?([0-9]+)[^0-9]*', r'\1.',a[0])))
        return choices

    def clean_volume_name(self):
        vname = self.cleaned_data['volume_name']
        if not re.search(r'^[a-z][-_.a-z0-9]*$', vname, re.I):
            raise forms.ValidationError(_("The volume name must start with letters and may include numbers, \"-\", \"_\" and \".\" ."))
        return vname

    def clean_group_type(self):
        if not self.cleaned_data.has_key('volume_disks') or \
                len(self.cleaned_data['volume_disks']) > 1 and self.cleaned_data['group_type'] in (None, ''):
            raise forms.ValidationError(_("This field is required."))
        return self.cleaned_data['group_type']

    def clean(self):
        cleaned_data = self.cleaned_data
        volume_name = cleaned_data.get("volume_name", "")
        disks =  cleaned_data.get("volume_disks")
        if cleaned_data.get("volume_fstype", None) not in ('ZFS', 'UFS'):
            msg = _(u"You must select a filesystem")
            self._errors["volume_fstype"] = self.error_class([msg])
            cleaned_data.pop("volume_fstype", None)
        if len(disks) == 0 and models.Volume.objects.filter(vol_name = volume_name).count() == 0:
            msg = _(u"This field is required")
            self._errors["volume_disks"] = self.error_class([msg])
            del cleaned_data["volume_disks"]
        if cleaned_data.get("volume_fstype", None) == 'UFS' and \
                models.Volume.objects.filter(vol_name = volume_name).count() > 0:
            msg = _(u"You already have a volume with same name")
            self._errors["volume_name"] = self.error_class([msg])
            del cleaned_data["volume_name"]

        if cleaned_data.get("volume_fstype", None) == 'ZFS':
            if volume_name in ('log',):
                msg = _(u"\"log\" is a reserved word and thus cannot be used")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)
            elif re.search(r'^c[0-9].*', volume_name) or re.search(r'^mirror.*', volume_name) or \
                re.search(r'^spare.*', volume_name) or re.search(r'^raidz.*', volume_name):
                msg = _(u"The volume name may NOT start with c[0-9], mirror, raidz or spare")
                self._errors["volume_name"] = self.error_class([msg])
                cleaned_data.pop("volume_name", None)

        return cleaned_data

    def done(self, request):
        # Construct and fill forms into database.
        volume_name = self.cleaned_data['volume_name']
        volume_fstype = self.cleaned_data['volume_fstype']
        disk_list = self.cleaned_data['volume_disks']
        force4khack = self.cleaned_data.get("force4khack", False)

        if (len(disk_list) < 2):
            if volume_fstype == 'ZFS':
                group_type = 'stripe'
            else:
                # UFS middleware expects no group_type for single disk volume
                group_type = ''
        else:
            group_type = self.cleaned_data['group_type']

        with transaction.commit_on_success():
            vols = models.Volume.objects.filter(vol_name = volume_name)
            if vols.count() == 1:
                volume = vols[0]
                add = True
            else:
                add = False
                volume = models.Volume(vol_name = volume_name, vol_fstype = volume_fstype)
                volume.save()

                mp = models.MountPoint(mp_volume=volume, mp_path='/mnt/' + volume_name, mp_options='rw')
                mp.save()
            self.volume = volume

            if len(disk_list) > 0:
                grpnum = models.DiskGroup.objects.filter(group_type = group_type, group_volume = volume).count()
                if grpnum > 0:
                    grp = models.DiskGroup(group_name=volume_name + group_type + str(grpnum), group_type = group_type, group_volume = volume)
                else:
                    grp = models.DiskGroup(group_name=volume_name + group_type, group_type = group_type, group_volume = volume)
                grp.save()

                for diskname in disk_list:
                    diskobj = models.Disk(disk_name = diskname, disk_identifier = "{devicename}%s" % diskname,
                                   disk_description = ("Member of %s %s" %
                                                      (volume_name, group_type)),
                                   disk_group = grp)
                    diskobj.save()

                if add:
                    notifier().zfs_volume_attach_group(grp, force4khack=force4khack)

            zpoolfields = re.compile(r'zpool_(.+)')
            disks = [(i, zpoolfields.search(i).group(1)) for i in request.POST.keys() \
                    if zpoolfields.match(i)]

            grouped = {}
            for key, disk in disks:
                if request.POST[key] in grouped:
                    grouped[request.POST[key]].append(disk)
                else:
                    grouped[request.POST[key]] = [disk,]

            for grp_type in grouped:

                if grp_type in ('log','cache','spare'):
                    # When doing log, we assume it's always 'mirror' for data safety
                    if grp_type == 'log' and len(grouped[grp_type]) > 1:
                        group_type='log mirror'
                    else:
                        group_type=grp_type
                    grpnum = models.DiskGroup.objects.filter(group_name=volume.vol_name+grp_type).count()
                    if grpnum > 0:
                        grp = models.DiskGroup(group_name=volume.vol_name+grp_type+str(grpnum), \
                            group_type=group_type , group_volume = volume)
                    else:
                        grp = models.DiskGroup(group_name=volume.vol_name+grp_type, \
                                group_type=group_type , group_volume = volume)
                    grp.save()

                    for diskname in grouped[grp_type]:
                        diskobj = models.Disk(disk_name = diskname,
                                       disk_identifier = "{devicename}%s" % diskname,
                                       disk_description = ("Member of %s %s" %
                                                          (volume.vol_name, group_type)),
                                       disk_group = grp
                                       )
                        diskobj.save()

                    if add:
                        notifier().zfs_volume_attach_group(grp, force4khack=force4khack)

            if not add:
                notifier().init("volume", volume, force4khack=force4khack)

        # This must be outside transaction block to make sure the changes are committed
        # before the call of ix-fstab
        notifier().reload("disk")

class VolumeImportForm(forms.Form):

    volume_name = forms.CharField(max_length = 30, label = _('Volume name') )
    volume_disks = forms.ChoiceField(choices=(), widget=forms.Select(attrs=attrs_dict), label = _('Member disk'))
    volume_fstype = forms.ChoiceField(choices = ((x, x) for x in ('UFS', 'NTFS', 'MSDOSFS', 'EXT2FS')), widget=forms.RadioSelect(attrs=attrs_dict), label = 'File System type')

    def __init__(self, *args, **kwargs):
        super(VolumeImportForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        self.fields['volume_disks'].choices.sort(key = lambda a : float(re.sub(r'^.*?([0-9]+)[^0-9]*', r'\1.',a[0])))

    def _populate_disk_choices(self):

        diskchoices = dict()
        used_disks = [notifier().identifier_to_device(i[0]) for i in models.Disk.objects.all().values_list('disk_identifier').distinct()]

        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        parts = notifier().get_partitions()

        for part in parts.keys():
            if len([i for i in used_disks if parts[part]['devname'].startswith(i)]) > 0:
                del parts[part]

        for part in parts:
            devname, capacity = parts[part]['devname'], parts[part]['capacity']
            capacity = humanize_size(capacity)
            diskchoices[devname] = "%s (%s)" % (devname, capacity)
        # Exclude the root device
        rootdev = popen("""glabel status | grep `mount | awk '$3 == "/" {print $1}' | sed -e 's/\/dev\///'` | awk '{print $3}'""").read().strip()
        rootdev_base = re.search('[a-z/]*[0-9]*', rootdev)
        if rootdev_base != None:
            for part in diskchoices.keys():
                if part.startswith(rootdev_base.group(0)):
                    del diskchoices[part]

        choices = diskchoices.items()
        choices.sort(key = lambda a : float(re.sub(r'^.*?([0-9]+)[^0-9]*', r'\1.',a[0])))
        return choices

    def clean(self):
        cleaned_data = self.cleaned_data
        volume_name = cleaned_data.get("volume_name")
        if models.Volume.objects.filter(vol_name = volume_name).count() > 0:
            msg = _(u"You already have a volume with same name")
            self._errors["volume_name"] = self.error_class([msg])
            del cleaned_data["volume_name"]

        isvalid = notifier().precheck_partition("/dev/%s" % cleaned_data.get('volume_disks', []), cleaned_data.get('volume_fstype', ''))
        if not isvalid:
            msg = _(u"The selected disks were not verified for this import rules.")
            self._errors["volume_name"] = self.error_class([msg])
            if cleaned_data.has_key("volume_name"):
                del cleaned_data["volume_name"]

        if cleaned_data.has_key("volume_name"):
            dolabel = notifier().label_disk(cleaned_data["volume_name"], "/dev/%s" % cleaned_data['volume_disks'], cleaned_data['volume_fstype'])
            if not dolabel:
                msg = _(u"Some error ocurred while labelling the disk.")
                self._errors["volume_name"] = self.error_class([msg])
                if cleaned_data.has_key("volume_name"):
                    del cleaned_data["volume_name"]

        return cleaned_data

    def done(self, request):
        # Construct and fill forms into database.
        volume_name = self.cleaned_data['volume_name']
        volume_fstype = self.cleaned_data['volume_fstype']
        disk_list = self.cleaned_data['volume_disks']

        volume = models.Volume(vol_name = volume_name, vol_fstype = volume_fstype)
        volume.save()
        self.volume = volume

        mp = models.MountPoint(mp_volume=volume, mp_path='/mnt/' + volume_name, mp_options='rw')
        mp.save()

        grp = models.DiskGroup(group_name= volume_name, group_type = '', group_volume = volume)
        grp.save()

        diskname = disk_list
        diskobj = models.Disk(disk_name = diskname, disk_identifier = "{devicename}%s" % diskname,
                       disk_description = ("Member of %s" %
                                          (volume_name)),
                       disk_group = grp)
        diskobj.save()

        notifier().reload("disk")

class VolumeAutoImportForm(forms.Form):

    #volume_name = forms.CharField(max_length = 30, label = _('Volume name') )
    volume_disks = forms.ChoiceField(choices=(), widget=forms.Select(attrs=attrs_dict), label = _('Member disk'))

    def __init__(self, *args, **kwargs):
        super(VolumeAutoImportForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()

    def _populate_disk_choices(self):

        diskchoices = dict()
        used_disks = [notifier().identifier_to_device(i[0]) for i in models.Disk.objects.all().values_list('disk_identifier').distinct()]

        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        vols = notifier().detect_volumes()

        for vol in list(vols):
            for vdev in vol['disks']['vdevs']:
                for disk in vdev['disks']:
                    if len([i for i in used_disks if i is not None and disk.startswith(i)]) > 0:
                        vols.remove(vol)
                        break

        for vol in vols:
            devname = "%s [%s]" % (vol['label'],vol['type'])
            diskchoices[vol['label']] = "%s" % (devname,)
        # Exclude the root device
        rootdev = popen("""glabel status | grep `mount | awk '$3 == "/" {print $1}' | sed -e 's/\/dev\///'` | awk '{print $3}'""").read().strip()
        rootdev_base = re.search('[a-z/]*[0-9]*', rootdev)
        if rootdev_base != None:
            for part in diskchoices.keys():
                if part.startswith(rootdev_base.group(0)):
                    del diskchoices[part]

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
            self._errors['__all__'] = self.error_class([_("You must select a volume.")])

        else:
            if models.Volume.objects.filter(vol_name = \
                        cleaned_data['volume']['label']).count() > 0:
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
                    msg = _(u"The selected disks were not verified for this import rules.")
                    self._errors["volume_disks"] = self.error_class([msg])
                    if cleaned_data.has_key("volume_disks"):
                        del cleaned_data["volume_disks"]
            elif cleaned_data['volume']['type'] == 'zfs':
                pass
            else:
                raise NotImplementedError

        return cleaned_data

    def done(self, request):

        vol = self.cleaned_data['volume']
        volume_name = vol['label']
        group_type = vol['group_type']
        if vol['type'] == 'geom':
            volume_fstype = 'UFS'
            grouped = {}
        elif vol['type'] == 'zfs':
            volume_fstype = 'ZFS'
            grouped = {
                    'log': vol['logs'],
                    'cache': vol['cache'],
                    'spare': vol['spare'],
                    }

        with transaction.commit_on_success():
            volume = models.Volume(vol_name = volume_name, vol_fstype = volume_fstype)
            volume.save()
            self.volume = volume

            mp = models.MountPoint(mp_volume=volume, mp_path='/mnt/' + volume_name, mp_options='rw')
            mp.save()

            if vol['type'] == 'zfs':

                i = 0
                for vdev in vol['disks']['vdevs']:
                    if i == 0:
                        group_name = volume_name
                    else:
                        group_name = volume_name + vdev['type'] + str(i)
                    grp = models.DiskGroup(group_name = group_name, group_type = vdev['type'],
                                group_volume = volume)
                    grp.save()

                    for diskname in vdev['disks']:
                        ident = notifier().device_to_identifier(diskname)
                        diskobj = models.Disk(disk_name = diskname, disk_identifier = ident,
                                       disk_description = ("Member of %s %s" %
                                                          (volume_name, vdev['type'])),
                                       disk_group = grp)
                        diskobj.save()
                    i += 1
            else:
                notifier().label_disk(volume_name, "%s/%s" % (group_type, volume_name), 'UFS')

                grp = models.DiskGroup(group_name= volume_name, group_type = group_type, group_volume = volume)
                grp.save()

                for diskname in vol['disks']['vdevs'][0]['disks']:
                    ident = notifier().device_to_identifier(diskname)
                    diskobj = models.Disk(disk_name = diskname, disk_identifier = ident,
                                   disk_description = ("Member of %s %s" %
                                                      (volume_name, group_type)),
                                   disk_group = grp)
                    diskobj.save()


            for grp_type in grouped:

                if grp_type in ('log','cache','spare') and grouped[grp_type]:
                    # When doing log, we assume it's always 'mirror' for data safety
                    if grp_type == 'log' and len(grouped[grp_type]) > 1:
                        group_type='log mirror'
                    else:
                        group_type=grp_type

                    i = 0
                    for vdev in grouped[grp_type]['vdevs']:
                        grp = models.DiskGroup(group_name=volume.vol_name+grp_type+str(i), \
                                group_type=group_type , group_volume = volume)
                        grp.save()

                        for diskname in vdev['disks']:
                            ident = notifier().device_to_identifier(diskname)
                            diskobj = models.Disk(disk_name = diskname, disk_identifier = ident,
                                      disk_description = ("Member of %s %s" %
                                        (volume.vol_name, grp_type)), disk_group = grp)
                            diskobj.save()
                        i += 1

            if vol['type'] == 'zfs' and not notifier().zfs_import(vol['label']):
                assert False, "Could not run zfs import"

        if vol['type'] == 'zfs':
            notifier().zfs_sync_datasets(volume)

        notifier().reload("disk")

#=================================

# A partial form for editing disk.
# we only show disk_name (used as GPT label), disk_disks
# (device name), and disk_group (which group this disk belongs
# to), but don't allow editing.
class DiskFormPartial(ModelForm):
    class Meta:
        model = models.Disk
    def __init__(self, *args, **kwargs):
        super(DiskFormPartial, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.id:
            self.fields['disk_name'].widget.attrs['readonly'] = True
            self.fields['disk_identifier'].widget.attrs['readonly'] = True
            self.fields['disk_group'].widget.attrs['readonly'] = True
    def clean_disk_name(self):
        return self.instance.disk_name
    def clean_disk_identifier(self):
        return self.instance.disk_identifier
    def clean_disk_group(self):
        return self.instance.disk_group


class ZFSDataset_CreateForm(Form):
    dataset_volid = forms.ChoiceField(choices=(), widget=forms.Select(attrs=attrs_dict),  label=_('Volume from which this dataset will be created on'))
    dataset_name = forms.CharField(max_length = 128, label = _('Dataset Name'))
    dataset_compression = forms.ChoiceField(choices=choices.ZFS_CompressionChoices, widget=forms.Select(attrs=attrs_dict), label=_('Compression level'))
    dataset_atime = forms.ChoiceField(choices=choices.ZFS_AtimeChoices, widget=forms.RadioSelect(attrs=attrs_dict), label=_('Enable atime'))
    dataset_refquota = forms.CharField(max_length = 128, initial=0, label=_('Quota for this dataset'), help_text=_('0=Unlimited; example: 1g'))
    dataset_quota = forms.CharField(max_length = 128, initial=0, label=_('Quota for this dataset and all children'), help_text=_('0=Unlimited; example: 1g'))
    dataset_refreserv = forms.CharField(max_length = 128, initial=0, label=_('Reserved space for this dataset'), help_text=_('0=None; example: 1g'))
    dataset_reserv = forms.CharField(max_length = 128, initial=0, label=_('Reserved space for this dataset and all children'), help_text=_('0=None; example: 1g'))
    def __init__(self, *args, **kwargs):
        super(ZFSDataset_CreateForm, self).__init__(*args, **kwargs)
        self.fields['dataset_volid'].choices = self._populate_volume_choices()
    def _populate_volume_choices(self):
        volumechoices = dict()
        volumes = models.Volume.objects.filter(vol_fstype='ZFS')
        for volume in volumes:
            volumechoices[volume.id] = volume.vol_name
        return volumechoices.items()
    def clean_dataset_name(self):
        name = self.cleaned_data["dataset_name"]
        if not re.search(r'^[a-zA-Z0-9][a-zA-Z0-9_\-:.]*(?:/[a-zA-Z0-9][a-zA-Z0-9_\-:.]+)*$', name):
            raise forms.ValidationError(_("Dataset names must begin with an alphanumeric character and may only contain (-), (_), (:) and (.)."))
        return name
    def clean(self):
        cleaned_data = self.cleaned_data
        volume_name = models.Volume.objects.get(id=cleaned_data.get("dataset_volid")).vol_name.__str__()
        full_dataset_name = "%s/%s" % (volume_name, cleaned_data.get("dataset_name").__str__())
        if len(notifier().list_zfs_datasets(path=full_dataset_name)) > 0:
            msg = _(u"You already have a dataset with the same name")
            self._errors["dataset_name"] = self.error_class([msg])
            del cleaned_data["dataset_name"]
        for field in ('dataset_refquota', 'dataset_quota', 'dataset_reserv', 'dataset_refreserv'):
            if not cleaned_data.has_key(field):
                cleaned_data[field] = ''
        r = re.compile('^(0|[1-9]\d*[mMgGtT]?)$')
        msg = _(u"Enter positive number (optionally suffixed by M, G, T), or, 0")
        if r.match(cleaned_data['dataset_refquota'].__str__())==None:
            self._errors['dataset_refquota'] = self.error_class([msg])
            del cleaned_data['dataset_refquota']
        if r.match(cleaned_data['dataset_quota'].__str__())==None:
            self._errors['dataset_quota'] = self.error_class([msg])
            del cleaned_data['dataset_quota']
        if r.match(cleaned_data['dataset_refreserv'].__str__())==None:
            self._errors['dataset_refreserv'] = self.error_class([msg])
            del cleaned_data['dataset_refreserv']
        if r.match(cleaned_data['dataset_reserv'].__str__())==None:
            self._errors['dataset_reserv'] = self.error_class([msg])
            del cleaned_data['dataset_reserv']
        return cleaned_data
    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data

class ZFSDataset_EditForm(Form):
    dataset_compression = forms.ChoiceField(choices=choices.ZFS_CompressionChoices, widget=forms.Select(attrs=attrs_dict), label=_('Compression level'))
    dataset_atime = forms.ChoiceField(choices=choices.ZFS_AtimeChoices, widget=forms.RadioSelect(attrs=attrs_dict), label=_('Enable atime'))
    dataset_refquota = forms.CharField(max_length = 128, initial=0, label=_('Quota for this dataset'), help_text=_('0=Unlimited; example: 1g'))
    dataset_quota = forms.CharField(max_length = 128, initial=0, label=_('Quota for this dataset and all children'), help_text=_('0=Unlimited; example: 1g'))
    dataset_refreserv = forms.CharField(max_length = 128, initial=0, label=_('Reserved space for this dataset'), help_text=_('0=None; example: 1g'))
    dataset_reserv = forms.CharField(max_length = 128, initial=0, label=_('Reserved space for this dataset and all children'), help_text=_('0=None; example: 1g'))

    def __init__(self, *args, **kwargs):
        self._mp = kwargs.pop("mp", None)
        dataset = self._mp.mp_path.replace("/mnt/","")
        super(ZFSDataset_EditForm, self).__init__(*args, **kwargs)
        data = notifier().zfs_get_options(dataset)
        self.fields['dataset_compression'].initial = data['compression']
        self.fields['dataset_atime'].initial = data['atime']
        if data['refquota'] == 'none':
            self.fields['dataset_refquota'].initial = 0
        else:
            self.fields['dataset_refquota'].initial = data['refquota']
        if data['quota'] == 'none':
            self.fields['dataset_quota'].initial = 0
        else:
            self.fields['dataset_quota'].initial = data['quota']
        if data['reservation'] == 'none':
            self.fields['dataset_reserv'].initial = 0
        else:
            self.fields['dataset_reserv'].initial = data['reservation']
        if data['refreservation'] == 'none':
            self.fields['dataset_refreserv'].initial = 0
        else:
            self.fields['dataset_refreserv'].initial = data['refreservation']

    def clean(self):
        cleaned_data = self.cleaned_data
        for field in ('dataset_refquota', 'dataset_quota', 'dataset_reserv', 'dataset_refreserv'):
            if not cleaned_data.has_key(field):
                cleaned_data[field] = ''
        r = re.compile('^(0|[1-9]\d*[mMgGtT]?)$')
        msg = _(u"Enter positive number (optionally suffixed by M, G, T), or, 0")
        if r.match(cleaned_data['dataset_refquota'].__str__())==None:
            self._errors['dataset_refquota'] = self.error_class([msg])
            del cleaned_data['dataset_refquota']
        if r.match(cleaned_data['dataset_quota'].__str__())==None:
            self._errors['dataset_quota'] = self.error_class([msg])
            del cleaned_data['dataset_quota']
        if r.match(cleaned_data['dataset_refreserv'].__str__())==None:
            self._errors['dataset_refreserv'] = self.error_class([msg])
            del cleaned_data['dataset_refreserv']
        if r.match(cleaned_data['dataset_reserv'].__str__())==None:
            self._errors['dataset_reserv'] = self.error_class([msg])
            del cleaned_data['dataset_reserv']
        return cleaned_data
    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data

class ZFSVolume_EditForm(Form):
    volume_compression = forms.ChoiceField(choices=choices.ZFS_CompressionChoices, widget=forms.Select(attrs=attrs_dict), label=_('Compression level'))
    volume_atime = forms.ChoiceField(choices=choices.ZFS_AtimeChoices, widget=forms.RadioSelect(attrs=attrs_dict), label=_('Enable atime'))
    volume_refquota = forms.CharField(max_length = 128, initial=0, label=_('Quota for this dataset'), help_text=_('0=Unlimited; example: 1g'))
    volume_refreserv = forms.CharField(max_length = 128, initial=0, label=_('Reserved space for this dataset'), help_text=_('0=None; example: 1g'))

    def __init__(self, *args, **kwargs):
        self._mp = kwargs.pop("mp", None)
        name = self._mp.mp_path.replace("/mnt/","")
        super(ZFSVolume_EditForm, self).__init__(*args, **kwargs)
        data = notifier().zfs_get_options(name)
        self.fields['volume_compression'].initial = data['compression']
        self.fields['volume_atime'].initial = data['atime']
        if data['refquota'] == 'none':
            self.fields['volume_refquota'].initial = 0
        else:
            self.fields['volume_refquota'].initial = data['refquota']
        if data['refreservation'] == 'none':
            self.fields['volume_refreserv'].initial = 0
        else:
            self.fields['volume_refreserv'].initial = data['refreservation']

    def clean(self):
        cleaned_data = self.cleaned_data
        r = re.compile('^(0|[1-9]\d*[mMgGtT]?)$')
        msg = _(u"Enter positive number (optionally suffixed by M, G, T), or, 0")
        if r.match(cleaned_data['volume_refquota'].__str__())==None:
            self._errors['volume_refquota'] = self.error_class([msg])
            del cleaned_data['volume_refquota']
        if r.match(cleaned_data['volume_refreserv'].__str__())==None:
            self._errors['volume_refreserv'] = self.error_class([msg])
            del cleaned_data['volume_refreserv']
        return cleaned_data
    def set_error(self, msg):
        msg = u"%s" % msg
        self._errors['__all__'] = self.error_class([msg])
        del self.cleaned_data

class ZVol_CreateForm(Form):
    zvol_volid = forms.ChoiceField(choices=(), widget=forms.Select(attrs=attrs_dict),  label=_('Volume from which this ZFS Volume will be created on'))
    zvol_name = forms.CharField(max_length = 128, label = _('ZFS Volume Name'))
    zvol_size = forms.CharField(max_length = 128, initial=0, label=_('Size for this ZFS Volume'), help_text=_('Example: 1g'))
    zvol_compression = forms.ChoiceField(choices=choices.ZFS_CompressionChoices, widget=forms.Select(attrs=attrs_dict), label=_('Compression level'))
    def __init__(self, *args, **kwargs):
        super(ZVol_CreateForm, self).__init__(*args, **kwargs)
        self.fields['zvol_volid'].choices = self._populate_volume_choices()
    def _populate_volume_choices(self):
        volumechoices = dict()
        volumes = models.Volume.objects.filter(vol_fstype='ZFS')
        for volume in volumes:
            volumechoices[volume.id] = volume.vol_name
        return volumechoices.items()
    def clean_dataset_name(self):
        name = self.cleaned_data["zvol_name"]
        if not re.search(r'^[a-zA-Z0-9][a-zA-Z0-9_\-:.]*$', name):
            raise forms.ValidationError(_("ZFS Volume names must begin with an alphanumeric character and may only contain (-), (_), (:) and (.)."))
        return name
    def clean(self):
        cleaned_data = self.cleaned_data
        volume_name = models.Volume.objects.get(id=cleaned_data.get("zvol_volid")).vol_name.__str__()
        full_zvol_name = "%s/%s" % (volume_name, cleaned_data.get("zvol_name").__str__())
        if len(notifier().list_zfs_datasets(path=full_zvol_name)) > 0:
            msg = _(u"You already have a dataset with the same name")
            self._errors["zvol_name"] = self.error_class([msg])
            del cleaned_data["zvol_name"]
        #r = re.compile('^(0|[1-9]\d*[mMgGtT]?)$')
        #msg = _(u"Enter positive number (optionally suffixed by M, G, T), or, 0")
        #if r.match(cleaned_data['dataset_refquota'].__str__())==None:
        #    self._errors['dataset_refquota'] = self.error_class([msg])
        #    del cleaned_data['dataset_refquota']
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
            import os
            if os.path.exists(os.path.join(path, ".windows")):
                self.fields['mp_acl'].initial = 'windows'
            else:
                self.fields['mp_acl'].initial = 'unix'
            user, group = notifier().mp_get_owner(path)
            self.fields['mp_mode'].initial = "%.3o" % notifier().mp_get_permission(path)
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
            'task_byweekday': CheckboxSelectMultiple(choices=choices.WEEKDAYS_CHOICES)
            #'task_bymonth': CheckboxSelectMultiple(choices=choices.MONTHS_CHOICES)
        }
    def __init__(self, *args, **kwargs):
        if len(args) > 0 and isinstance(args[0], QueryDict):
            new = args[0].copy()
            HOUR = re.compile(r'(?P<hour>\d{2}):(?P<min>\d{2}):(?P<sec>\d{2})')
            if new.has_key("task_begin"):
                search = HOUR.search(new['task_begin'])
                new['task_begin'] = time(hour=int(search.group("hour")),
                                           minute=int(search.group("min")),
                                           second=int(search.group("sec")))
            if new.has_key("task_end"):
                search = HOUR.search(new['task_end'])
                new['task_end'] = time(hour=int(search.group("hour")),
                                           minute=int(search.group("min")),
                                           second=int(search.group("sec")))
            args = (new,) + args[1:]
        super(PeriodicSnapForm, self).__init__(*args, **kwargs)
        #self.fields['task_repeat_unit'].widget = forms.Select(choices=choices.RepeatUnit_Choices, attrs={'onChange': 'taskrepeat_checkings();'})
        self.fields['task_repeat_unit'].widget = forms.HiddenInput()

    def clean(self):
        cdata = self.cleaned_data
        if cdata['task_repeat_unit'] == 'weekly' and len(cdata['task_byweekday']) == 0:
            self._errors['task_byweekday'] = self.error_class([_("At least one day must be chosen"),])
            del cdata['task_byweekday']
        return cdata

class ManualSnapshotForm(Form):
    ms_recursively = forms.BooleanField(initial=False,required=False,label=_('Recursive snapshot'))
    ms_name = forms.CharField(label=_('Snapshot Name'))
    def __init__(self, *args, **kwargs):
        super(ManualSnapshotForm, self).__init__(*args, **kwargs)
        self.fields['ms_name'].initial = datetime.today().strftime('manual-%Y%m%d')
    def clean_ms_name(self):
        regex = re.compile('^[-a-zA-Z0-9_.]+$')
        if regex.match(self.cleaned_data['ms_name'].__str__()) is None:
            raise forms.ValidationError(_("Only [-a-zA-Z0-9_.] permitted as snapshot name"))
        return self.cleaned_data['ms_name']
    def commit(self, path):
        # TODO: Better handling of the path parameter, ideally change it to supply
        # dataset instead.
        if path.startswith('/mnt/'):
            dataset = path.__str__()[5:]
        elif path.startswith('mnt/'):
            dataset = path.__str__()[4:]
        else:
            raise(ValueError(_('Invalid prefix')))
        notifier().zfs_mksnap(dataset, self.cleaned_data['ms_name'].__str__(), self.cleaned_data['ms_recursively'])

class CloneSnapshotForm(Form):
    cs_snapshot = forms.CharField(label=_('Snapshot'))
    cs_name = forms.CharField(label=_('Clone Name (must be on same volume)'))
    def __init__(self, *args, **kwargs):
        super(CloneSnapshotForm, self).__init__(*args, **kwargs)
        self.fields['cs_snapshot'].widget.attrs['readonly'] = True
        self.fields['cs_snapshot'].initial = kwargs['initial']['cs_snapshot']
        self.fields['cs_snapshot'].value = kwargs['initial']['cs_snapshot']
        dataset, snapname = kwargs['initial']['cs_snapshot'].split('@')
        self.fields['cs_name'].initial = '%s/clone-%s' % (dataset, snapname)
    def clean_cs_snapshot(self):
        return self.fields['cs_snapshot'].initial
    def clean_cs_name(self):
        regex = re.compile('^[-a-zA-Z0-9_./]+$')
        if regex.match(self.cleaned_data['cs_name'].__str__()) is None:
            raise forms.ValidationError(_("Only [-a-zA-Z0-9_./] permitted as clone name"))
        if '/' in self.fields['cs_snapshot'].initial:
            volname = self.fields['cs_snapshot'].initial.split('/')[0]
        else:
            volname = self.fields['cs_snapshot'].initial.split('@')[0]
        if not self.cleaned_data['cs_name'].startswith('%s/' % (volname)):
            raise forms.ValidationError(_("Clone must be within the same volume"))
        return self.cleaned_data['cs_name']
    def commit(self):
        snapshot = self.cleaned_data['cs_snapshot'].__str__()
        retval = notifier().zfs_clonesnap(snapshot, self.cleaned_data['cs_name'].__str__())
        if retval == '':
            if '/' in self.fields['cs_snapshot'].initial:
                zfs = self.fields['cs_snapshot'].initial.split('/')[0]
            else:
                zfs = self.fields['cs_snapshot'].initial.split('@')[0]
            volume = models.Volume.objects.get(vol_name=zfs)
            mp = models.MountPoint(mp_volume=volume, mp_path='/mnt/%s' % (self.cleaned_data['cs_name']), mp_options='noauto', mp_ischild=True)
            mp.save()
        return retval

class DiskReplacementForm(forms.Form):

    volume_disks = forms.ChoiceField(choices=(), widget=forms.Select(attrs=attrs_dict), label = _('Member disk'))

    def __init__(self, *args, **kwargs):
        self.disk = kwargs.pop('disk')
        super(DiskReplacementForm, self).__init__(*args, **kwargs)
        self.fields['volume_disks'].choices = self._populate_disk_choices()
        self.fields['volume_disks'].choices.sort(key = lambda a : float(re.sub(r'^.*?([0-9]+)[^0-9]*', r'\1.',a[0])))

    def _populate_disk_choices(self):

        diskchoices = dict()
        used_disks = [i[0] for i in models.Disk.objects.exclude(disk_name=self.disk.disk_name).values_list('disk_name').distinct()]

        # Grab partition list
        # NOTE: This approach may fail if device nodes are not accessible.
        disks = notifier().get_disks()

        for disk in disks.keys():
            if len([i for i in used_disks if disks[disk]['devname'].startswith(i)]) > 0:
                del disks[disk]

        for disk in disks:
            devname, capacity = disks[disk]['devname'], disks[disk]['capacity']

            capacity = int(capacity)
            if capacity >= 1099511627776:
                    capacity = "%.1f TiB" % (capacity / 1099511627776.0)
            elif capacity >= 1073741824:
                    capacity = "%.1f GiB" % (capacity / 1073741824.0)
            elif capacity >= 1048576:
                    capacity = "%.1f MiB" % (capacity / 1048576.0)
            else:
                    capacity = "%d Bytes" % (capacity)
            if devname == self.disk.disk_name:
                diskchoices[devname] = "In-place [%s (%s)]" % (devname, capacity)
            else:
                diskchoices[devname] = "%s (%s)" % (devname, capacity)
        # Exclude the root device
        rootdev = popen("""glabel status | grep `mount | awk '$3 == "/" {print $1}' | sed -e 's/\/dev\///'` | awk '{print $3}'""").read().strip()
        rootdev_base = re.search('[a-z/]*[0-9]*', rootdev)
        if rootdev_base != None:
            for disk in diskchoices.keys():
                if disk.startswith(rootdev_base.group(0)):
                    del diskchoices[disk]

        choices = diskchoices.items()
        choices.sort(key = lambda a : float(re.sub(r'^.*?([0-9]+)[^0-9]*', r'\1.',a[0])))
        return choices
    def done(self, volume, fromdisk):
        with transaction.commit_on_success():
            devname = self.cleaned_data['volume_disks']
            if devname != fromdisk.identifier_to_device():
                disk = models.Disk()
                disk.disk_name = devname
                disk.disk_identifier = "{devicename}%s" % devname
                disk.disk_group = fromdisk.disk_group
                disk.disk_description = fromdisk.disk_description
                disk.save()
                if volume.vol_fstype == 'ZFS':
                    rv = notifier().zfs_replace_disk(volume, fromdisk, disk)
                elif volume.vol_fstype == 'UFS':
                    rv = notifier().geom_disk_replace(volume, fromdisk, disk)
            else:
                if volume.vol_fstype == 'ZFS':
                    rv = notifier().zfs_replace_disk(volume, fromdisk, fromdisk)
                elif volume.vol_fstype == 'UFS':
                    rv = notifier().geom_disk_replace(volume, fromdisk, fromdisk)
            if rv == 0:
                if devname != fromdisk.identifier_to_device():
                    if volume.vol_fstype == 'ZFS':
                        dg = models.DiskGroup.objects.filter(group_volume=volume,group_type='detached')
                        if dg.count() == 0:
                            dg = models.DiskGroup()
                            dg.group_volume = volume
                            dg.group_name = "%sdetached" % volume.vol_name
                            dg.group_type = 'detached'
                            dg.save()
                        else:
                            dg = dg[0]
                        fromdisk.disk_group = dg
                        fromdisk.save()
                    elif volume.vol_fstype == 'UFS':
                        fromdisk.delete()
                return True
            else:
                if devname != fromdisk.identifier_to_device():
                    disk.delete()
                return False

class ReplicationForm(ModelForm):
    remote_hostname = forms.CharField(_("Remote hostname"),)
    remote_hostkey = forms.CharField(_("Remote hostkey"),widget=forms.Textarea())
    class Meta:
        model = models.Replication
        exclude = ('repl_lastsnapshot','repl_remote')
    def __init__(self, *args, **kwargs):
        repl = kwargs.get('instance', None)
        super(ReplicationForm, self).__init__(*args, **kwargs)
        self.fields['repl_mountpoint'].queryset = self.fields['repl_mountpoint'].queryset.filter(task__in=models.Task.objects.all()).distinct()
        if repl != None and repl.id != None:
            self.fields['remote_hostname'].initial = repl.repl_remote.ssh_remote_hostname
            self.fields['remote_hostkey'].initial = repl.repl_remote.ssh_remote_hostkey
    def save(self):
        if self.instance.id == None:
            r = models.ReplRemote()
        else:
            r = self.instance.repl_remote
        r.ssh_remote_hostname = self.cleaned_data.get("remote_hostname")
        r.ssh_remote_hostkey = self.cleaned_data.get("remote_hostkey")
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

