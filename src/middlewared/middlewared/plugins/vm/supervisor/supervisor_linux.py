from middlewared.plugins.vm.devices import CDROM, DISK, DISPLAY, PCI, RAW
from middlewared.utils import Nid

from .supervisor_base import VMSupervisorBase
from .utils import create_element


class VMSupervisor(VMSupervisorBase):

    def construct_xml(self):
        return create_element(
            'domain', type='kvm', id=str(self.vm_data['id']), attribute_dict={'children': self.get_domain_children()}
        )

    def commandline_xml(self):
        return []

    def os_xml(self):
        children = [create_element('type', attribute_dict={'text': 'hvm'})]
        if self.vm_data['bootloader'] == 'UEFI':
            children.append(
                create_element(
                    'loader', attribute_dict={'text': '/usr/share/OVMF/OVMF_CODE.fd'}, readonly='yes', type='pflash',
                )
            )
        return [create_element('os', attribute_dict={'children': children})]

    def devices_xml(self):
        boot_no = Nid(1)
        scsi_device_no = Nid(1)
        virtual_device_no = Nid(1)
        devices = []
        for device in filter(lambda d: d.is_available(), self.devices):
            if isinstance(device, (DISK, CDROM, RAW)):
                if device.data['attributes'].get('type') == 'VIRTIO':
                    disk_no = virtual_device_no()
                else:
                    disk_no = scsi_device_no()
                device_xml = device.xml(disk_number=disk_no, boot_number=boot_no())
            else:
                device_xml = device.xml()
            devices.extend(device_xml if isinstance(device_xml, (tuple, list)) else [device_xml])

        if not any(isinstance(device, DISPLAY) for device in self.devices):
            # We should add a video device if there is no display device configured because most by
            # default if not all headless servers like ubuntu etc require it to boot
            devices.append(create_element('video'))

        devices.append(create_element('serial', type='pty'))
        return create_element('devices', attribute_dict={'children': devices})

    def cpu_xml(self):
        cpu_elem = super().cpu_xml()
        if self.vm_data['cpu_mode'] != 'CUSTOM':
            cpu_elem.set('mode', self.vm_data['cpu_mode'].lower())
        elif self.vm_data['cpu_model']:
            cpu_model = self.middleware.call_sync('vm.cpu_model_choices').get(self.vm_data['cpu_model'])
            if cpu_model:
                # Right now this is best effort for the domain to start with specified CPU Model and not fallback
                # However if some features are missing in the host, qemu will right now still start the domain
                # and mark them as missing. We should perhaps make this configurable in the future to control
                # if domain should/should not be started
                cpu_elem.append(
                    create_element(
                        'model', fallback='forbid', attribute_dict={'text': self.vm_data['cpu_model']}
                    )
                )
        return cpu_elem
