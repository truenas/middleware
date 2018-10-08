import logging
import os

from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _

from dojango import forms
from freenasUI import choices
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

    root_password = forms.CharField(
        label=_("Root Password"),
        widget=forms.PasswordInput(render_value=True),
        required=False,
    )
    path = PathField(
        label=_("Docker Disk File"),
        dirsonly=False,
        filesonly=False,
    )
    size = forms.IntegerField(
        label=_("Size of Docker Disk File (GiB)"),
        initial=20,
        required=False,
    )

    class Meta:
        fields = '__all__'
        model = models.VM

    def __init__(self, *args, **kwargs):
        super(VMForm, self).__init__(*args, **kwargs)
        if self.instance.id:
            for i in ('vm_type', 'root_password', 'path', 'size'):
                del self.fields[i]
            if self.instance.vm_type != 'Bhyve':
                del self.fields['bootloader']
        else:
            self.fields['vm_type'].widget.attrs['onChange'] = ("vmTypeToggle();")
            key_order(self, 0, 'vm_type', instance=True)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.replace(' ', '')
        return name

    def clean_root_password(self):
        vm_type = self.cleaned_data.get('vm_type')
        root_password = self.cleaned_data.get('root_password')
        if vm_type != 'Bhyve' and not root_password:
            raise forms.ValidationError(_('This field is required.'))
        return root_password

    def clean_path(self):
        vm_type = self.cleaned_data.get('vm_type')
        path = self.cleaned_data.get('path')
        if vm_type != 'Bhyve':
            if path and os.path.exists(path):
                raise forms.ValidationError(_('File must not exist.'))
            elif not path:
                raise forms.ValidationError(_('File path is required.'))
        return path

    def clean_size(self):
        vm_type = self.cleaned_data.get('vm_type')
        size = self.cleaned_data.get('size')
        if vm_type != 'Bhyve' and not size:
            raise forms.ValidationError(_('This field is required.'))
        return size

    def save(self, **kwargs):
        with client as c:
            cdata = self.cleaned_data

            # Container boot load is GRUB
            if self.instance.vm_type == 'Container Provider':
                cdata['bootloader'] = 'GRUB'

            if self.instance.id:
                c.call('vm.update', self.instance.id, cdata)
            else:
                if cdata['vm_type'] == 'Container Provider':
                    cdata['devices'] = [
                        {'dtype': 'NIC', 'attributes': {'type': 'E1000'}},
                        {'dtype': 'RAW', 'attributes': {
                            'path': cdata.pop('path'),
                            'type': 'AHCI',
                            'sectorsize': 0,
                            'size': cdata.pop('size'),
                            'exists': False,
                        }},
                    ]
                    cdata.pop('vm_type')
                    cdata.pop('bootloader')
                    cdata['type'] = 'RancherOS'
                    return c.call('vm.create_container', cdata)

                cdata.pop('root_password')
                cdata.pop('path')
                cdata.pop('size')

                if cdata['bootloader'] == 'UEFI' and cdata['vm_type'] == 'Bhyve':
                    cdata['devices'] = [
                        {'dtype': 'NIC', 'attributes': {'type': 'E1000'}},
                        {'dtype': 'VNC', 'attributes': {'wait': False, 'vnc_web': False}},
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
    DISK_raw = PathField(
        label=_('Raw File'),
        required=False,
        dirsonly=False,
    )
    DISK_raw_boot = forms.BooleanField(
        label=_('Disk boot'),
        widget=forms.widgets.HiddenInput(),
        required=False,
        initial=False,
    )
    ROOT_password = forms.CharField(
        label=_('Password'),
        max_length=50,
        widget=forms.widgets.HiddenInput(),
        required=False,
        help_text=_("Set the password for the rancher user."),
    )
    DISK_sectorsize = forms.IntegerField(
        label=_('Disk sectorsize'),
        required=False,
        initial=0,
        help_text=_("Sector size of the emulated disk in bytes. Both logical and physical sector size are set to this value."
                    "If 0, a sector size is not set."),
    )
    DISK_raw_size = forms.CharField(
        label=_('Disk size'),
        widget=forms.widgets.HiddenInput(),
        required=False,
        initial=0,
        validators=[RegexValidator("^(\d*)\s?([M|G|T]?)$", "Enter M, G, or T after the value to use megabytes, gigabytes or terabytes."
                                                           " When no suffix letter is entered, the units default to gigabytes.")],
        help_text=_("Resize the existing raw disk. Enter 0 to use the disk with the current size."),
    )
    NIC_type = forms.ChoiceField(
        label=_('Adapter Type'),
        choices=choices.VM_NICTYPES,
        required=False,
        initial='E1000',
    )
    NIC_attach = forms.ChoiceField(
        label=_('NIC to attach'),
        choices=choices.NICChoices(exclude_configured=False),
        required=False,
    )
    NIC_mac = forms.CharField(
        label=_('MAC Address'),
        required=False,
        help_text=_("Specify the adapter MAC Address or leave empty to be auto generated."),
        validators=[RegexValidator("^([0-9a-fA-F]{2}([::]?|$)){6}$", "Invalid MAC format.")],
        initial='00:a0:98:FF:FF:FF',
    )
    VNC_resolution = forms.ChoiceField(
        label=_('Resolution'),
        choices=choices.VNC_RESOLUTION,
        required=False,
        initial='1024x768',
    )
    VNC_port = forms.CharField(
        label=_('VNC port'),
        required=False,
        help_text=_("Specify the VNC port or set to 0 for auto."),
        validators=[RegexValidator("^[0-9]*$", "Only integers are accepted")],
        initial=0,
    )
    VNC_bind = forms.ChoiceField(
        label=_('Bind to'),
        choices=(),
        required=False,
    )
    VNC_wait = forms.BooleanField(
        label=_('Wait to boot'),
        required=False,
    )
    VNC_password = forms.CharField(
        label=_('Password'),
        max_length=8,
        widget=forms.PasswordInput(render_value=True,),
        required=False,
        help_text=_("The VNC password authentication."
                    "Maximum password length is 8 characters.")
    )
    VNC_web = forms.BooleanField(
        label=_('VNC Web'),
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

        self.fields['VNC_bind'].choices = self.ipv4_list()

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
                self.fields['DISK_sectorsize'].initial = self.instance.attributes.get('sectorsize', 0)
            elif self.instance.dtype == 'RAW':
                self.fields['DISK_raw'].initial = self.instance.attributes.get('path', '')
                self.fields['DISK_mode'].initial = self.instance.attributes.get('type')
                self.fields['DISK_sectorsize'].initial = self.instance.attributes.get('sectorsize', 0)

                if self.instance.vm.vm_type == 'Container Provider':
                    self.fields['DISK_raw_boot'].widget = forms.CheckboxInput()
                    self.fields['DISK_raw_size'].widget = forms.TextInput()
                    self.fields['ROOT_password'].widget = forms.PasswordInput(render_value=True,)

                self.fields['DISK_raw_boot'].initial = self.instance.attributes.get('boot', False)
                self.fields['DISK_raw_size'].initial = self.instance.attributes.get('size', '')
                self.fields['ROOT_password'].initial = self.instance.attributes.get('rootpwd', '')
            elif self.instance.dtype == 'NIC':
                self.fields['NIC_type'].initial = self.instance.attributes.get('type')
                self.fields['NIC_mac'].initial = self.instance.attributes.get('mac')
                self.fields['NIC_attach'].initial = self.instance.attributes.get('nic_attach')
            elif self.instance.dtype == 'VNC':
                vnc_port = self.instance.attributes.get('vnc_port')
                vnc_port = 0 if vnc_port is None else vnc_port

                self.fields['VNC_wait'].initial = self.instance.attributes.get('wait')
                self.fields['VNC_port'].initial = vnc_port
                self.fields['VNC_resolution'].initial = self.instance.attributes.get('vnc_resolution')
                self.fields['VNC_bind'].initial = self.instance.attributes.get('vnc_bind')
                self.fields['VNC_password'].initial = self.instance.attributes.get('vnc_password')
                self.fields['VNC_web'].initial = self.instance.attributes.get('vnc_web')

    def ipv4_list(self):
        choices = ()
        with client as c:
            ipv4_addresses = c.call('vm.get_vnc_ipv4')
        for ipv4_addr in ipv4_addresses:
            choices = choices + ((ipv4_addr, ipv4_addr),)
        return choices

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
                'sectorsize': self.cleaned_data['DISK_sectorsize'],
            }
        elif self.cleaned_data['dtype'] == 'RAW':
            obj.attributes = {
                'path': self.cleaned_data['DISK_raw'],
                'type': self.cleaned_data['DISK_mode'],
                'sectorsize': self.cleaned_data['DISK_sectorsize'],
                'boot': self.cleaned_data['DISK_raw_boot'],
                'size': self.cleaned_data['DISK_raw_size'],
                'rootpwd': self.cleaned_data['ROOT_password'],
            }
        elif self.cleaned_data['dtype'] == 'CDROM':
            cdrom_path = self.cleaned_data['CDROM_path']
            if cdrom_path:
                obj.attributes = {
                    'path': cdrom_path,
                }
            else:
                self._errors['CDROM_path'] = self.error_class([_('Please choose an ISO file.')])
        elif self.cleaned_data['dtype'] == 'NIC':
            obj.attributes = {
                'type': self.cleaned_data['NIC_type'],
                'mac': self.cleaned_data['NIC_mac'],
                'nic_attach': self.cleaned_data['NIC_attach'],
            }
        elif self.cleaned_data['dtype'] == 'VNC':
            if vm.bootloader == 'UEFI' and self.is_container(vm.vm_type) is False:
                obj.attributes = {
                    'wait': self.cleaned_data['VNC_wait'],
                    'vnc_port': self.cleaned_data['VNC_port'],
                    'vnc_resolution': self.cleaned_data['VNC_resolution'],
                    'vnc_bind': self.cleaned_data['VNC_bind'],
                    'vnc_password': self.cleaned_data['VNC_password'],
                    'vnc_web': self.cleaned_data['VNC_web'],
                }
            else:
                self._errors['dtype'] = self.error_class([_('VNC only works with UEFI VMs')])
                self.cleaned_data.pop('VNC_port', None)
                self.cleaned_data.pop('VNC_wait', None)
                self.cleaned_data.pop('VNC_resolution', None)
                self.cleaned_data.pop('VNC_bind', None)
                self.cleaned_data.pop('VNC_password', None)
                self.cleaned_data.pop('VNC_web', None)
                return obj

        obj.save()
        return obj
