import logging
import re

from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
from freenasUI.common import humanize_size
from freenasUI.common.forms import ModelForm
from freenasUI.freeadmin.forms import PathField
from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.vm import models

log = logging.getLogger('vm.forms')


class VMForm(ModelForm):

    class Meta:
        fields = '__all__'
        model = models.VM

    def get_cpu_flags(self):
        cpu_flags = {}
        with client as c:
            cpu_flags = c.call('vm.flags')
        return cpu_flags

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            if not re.search(r'^[a-zA-Z _0-9]+$', name):
                raise forms.ValidationError(_('Only alphanumeric characters are allowed and maximum of 150 characters.'))
            name = name.replace(' ', '')
        return name

    def clean_vcpus(self):
        cpu_flags = self.get_cpu_flags()
        vcpus = self.cleaned_data.get('vcpus')

        if cpu_flags.get('intel_vmx'):
            if vcpus > 1 and cpu_flags.get('unrestricted_guest') is False:
                raise forms.ValidationError(_('Only one Virtual CPU is allowed in this system.'))
            else:
                return vcpus
        elif cpu_flags.get('amd_rvi'):
            if vcpus > 1 and cpu_flags.get('amd_asids') is False:
                raise forms.ValidationError(_('Only one Virtual CPU is allowed in this system.'))
            else:
                return vcpus

    def save(self, **kwargs):
        with client as c:
            cdata = self.cleaned_data
            if self.instance.id:
                c.call('vm.update', self.instance.id, cdata)
            else:
                if self.instance.bootloader == 'UEFI':
                    cdata['devices'] = [
                        {'dtype': 'NIC', 'attributes': {'type': 'E1000'}},
                        {'dtype': 'VNC', 'attributes': {'wait': True}},
                    ]
                else:
                    cdata['devices'] = [
                        {'dtype': 'NIC', 'attributes': {'type': 'E1000'}},
                    ]
                self.instance = models.VM.objects.get(pk=c.call('vm.create', cdata))
        return self.instance

    def delete(self, **kwargs):
        with client as c:
            c.call('vm.delete', self.instance.id)


class DeviceForm(ModelForm):

    CDROM_path = PathField(
        label=_('CD-ROM (ISO)'),
        required=False,
        dirsonly=False,
    )
    DISK_zvol = forms.ChoiceField(
        label=_('ZVol'),
        required=False,
    )
    DISK_mode = forms.ChoiceField(
        label=_('Mode'),
        choices=choices.VM_DISKMODETYPES,
        required=False,
        initial='AHCI',
    )
    NIC_type = forms.ChoiceField(
        label=_('Adapter Type'),
        choices=choices.VM_NICTYPES,
        required=False,
        initial='E1000',
    )
    NIC_mac = forms.CharField(
        label=_('Mac Address'),
        required=False,
        help_text=_("You can specify the adapter MAC Address or let it be auto generated."),
        validators=[RegexValidator("^([0-9a-fA-F]{2}([::]?|$)){6}$", "Invalid MAC format.")],
        initial='00:a0:98:FF:FF:FF',
    )
    VNC_port = forms.CharField(
        label=_('VNC port'),
        required=False,
        initial=0,
        help_text=_("You can specify the VNC port or 0 for auto."),
        validators=[RegexValidator("^[0-9]*$", "Only integer is accepted")],
    )
    VNC_wait = forms.BooleanField(
        label=_('Wait to boot'),
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.Device

    def __init__(self, *args, **kwargs):
        super(DeviceForm, self).__init__(*args, **kwargs)
        self.fields['dtype'].widget.attrs['onChange'] = (
            "deviceTypeToggle();"
        )

        diskchoices = {}
        _n = notifier()
        used_zvol = []
        for volume in Volume.objects.filter():
            zvols = _n.list_zfs_vols(volume.vol_name, sort='name')
            for zvol, attrs in zvols.items():
                if "zvol/" + zvol not in used_zvol:
                    diskchoices["zvol/" + zvol] = "%s (%s)" % (
                        zvol,
                        humanize_size(attrs['volsize']))
        self.fields['DISK_zvol'].choices = diskchoices.items()

        if self.instance.id:
            if self.instance.dtype == 'CDROM':
                self.fields['CDROM_path'].initial = self.instance.attributes.get('path', '')
            elif self.instance.dtype == 'DISK':
                self.fields['DISK_zvol'].initial = self.instance.attributes.get('path', '').replace('/dev/', '')
                self.fields['DISK_mode'].initial = self.instance.attributes.get('type')
            elif self.instance.dtype == 'NIC':
                self.fields['NIC_type'].initial = self.instance.attributes.get('type')
                self.fields['NIC_mac'].initial = self.instance.attributes.get('mac')
            elif self.instance.dtype == 'VNC':
                self.fields['VNC_wait'].initial = self.instance.attributes.get('wait')
                self.fields['VNC_port'].initial = self.instance.attributes.get('vnc_port')

    def clean(self):
        vm = self.cleaned_data.get('vm')
        vnc_port = self.cleaned_data.get('VNC_port')
        new_vnc_port = 5900
        if vm and vnc_port == '0':
            new_vnc_port = new_vnc_port + int(vm.id)
            self.cleaned_data['VNC_port'] = str(new_vnc_port)

        return self.cleaned_data

    def save(self, *args, **kwargs):
        vm = self.cleaned_data.get('vm')
        kwargs['commit'] = False
        obj = super(DeviceForm, self).save(*args, **kwargs)
        if self.cleaned_data['dtype'] == 'DISK':
            obj.attributes = {
                'path': '/dev/' + self.cleaned_data['DISK_zvol'],
                'type': self.cleaned_data['DISK_mode'],
            }
        elif self.cleaned_data['dtype'] == 'CDROM':
            obj.attributes = {
                'path': self.cleaned_data['CDROM_path'],
            }
        elif self.cleaned_data['dtype'] == 'NIC':
            obj.attributes = {
                'type': self.cleaned_data['NIC_type'],
                'mac': self.cleaned_data['NIC_mac'],
            }
        elif self.cleaned_data['dtype'] == 'VNC':
            if vm.bootloader == 'UEFI':
                obj.attributes = {
                    'wait': self.cleaned_data['VNC_wait'],
                    'vnc_port': self.cleaned_data['VNC_port'],
                }
            else:
                self._errors['dtype'] = self.error_class([_('VNC is only allowed for UEFI')])
                self.cleaned_data.pop('VNC_port', None)
                self.cleaned_data.pop('VNC_wait', None)
                return obj

        obj.save()
        return obj
