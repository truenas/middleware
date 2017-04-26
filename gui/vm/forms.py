import logging
import re

from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI.common import humanize_size
from freenasUI.common.forms import ModelForm
from freenasUI.freeadmin.forms import PathField
from freenasUI.freeadmin.utils import key_order
from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier
from freenasUI.storage.models import Volume
from freenasUI.vm import models

log = logging.getLogger('vm.forms')


class VMForm(ModelForm):


    class Meta:
        fields = '__all__'
        model = models.VM

    def __init__(self, *args, **kwargs):
        super(VMForm, self).__init__(*args, **kwargs)
        self.fields['vm_type'].widget.attrs['onChange'] = ("vmTypeToggle();")
        key_order(self, 0, 'vm_type', instance=True)
        key_order(self, 1, 'container_type', instance=True)
        key_order(self, 6, 'container_path', instance=True)

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
            if self.instance.vm_type == 'Bhyve':
                cdata['container_type'] = "None"

            if self.instance.id:
                c.call('vm.update', self.instance.id, cdata)
                pk = self.instance.id
            else:
                if self.instance.bootloader == 'UEFI' and self.instance.vm_type != 'Container Provider':
                    cdata['devices'] = [
                        {'dtype': 'NIC', 'attributes': {'type': 'E1000'}},
                        {'dtype': 'VNC', 'attributes': {'wait': True}},
                    ]
                else:
                    cdata['devices'] = [
                        {'dtype': 'NIC', 'attributes': {'type': 'E1000'}},
                    ]
                pk = c.call('vm.create', cdata)
        return models.VM.objects.get(pk=pk)

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
        choices=(
            ('AHCI', _('AHCI')),
            ('VIRTIO', _('VirtIO')),
        ),
        required=False,
        initial='AHCI',
    )
    NIC_type = forms.ChoiceField(
        label=_('Adapter Type'),
        choices=(
            ('E1000', _('Intel e82545 (e1000)')),
            ('VIRTIO', _('VirtIO')),
        ),
        required=False,
        initial='E1000',
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

    def is_container(self, vm_type):
        if vm_type == 'Container Provider':
            return True
        else:
            return False

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
            if self.is_container(vm.vm_type):
                self._errors['dtype'] = self.error_class([_('Not allowed to add a CDROM on VM Container')])
            obj.attributes = {
                'path': self.cleaned_data['CDROM_path'],
            }
        elif self.cleaned_data['dtype'] == 'NIC':
            obj.attributes = {
                'type': self.cleaned_data['NIC_type'],
            }
        elif self.cleaned_data['dtype'] == 'VNC':
            if vm.bootloader == 'UEFI' and self.is_container is False:
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
