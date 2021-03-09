import os

from lxml import etree

from middlewared.plugins.vm.devices import CDROM, DISK, NIC, PCI, RAW, DISPLAY
from middlewared.service import CallError
from middlewared.utils import Nid

from .supervisor_base import VMSupervisorBase
from .utils import create_element


LIBVIRT_BHYVE_NAMESPACE = 'http://libvirt.org/schemas/domain/bhyve/1.0'
LIBVIRT_BHYVE_NSMAP = {'bhyve': LIBVIRT_BHYVE_NAMESPACE}


class VMSupervisor(VMSupervisorBase):

    def os_xml(self):
        os_list = []
        children = [create_element('type', attribute_dict={'text': 'hvm'})]
        if self.vm_data['bootloader'] in ('UEFI', 'UEFI_CSM'):
            children.append(
                create_element(
                    'loader', attribute_dict={
                        'text': '/usr/local/share/uefi-firmware/BHYVE_UEFI'
                                f'{"_CSM" if self.vm_data["bootloader"] == "UEFI_CSM" else ""}.fd'
                    }, readonly='yes', type='pflash',
                ),
            )

        if self.vm_data['bootloader'] == 'GRUB':
            # Following is keeping compatibility with old code where we supported rancher/docker
            # We can have two cases where the user has the path set pointing to his/her grub file or where
            # the data inside grubconfig is saved and we write out a new file for it
            # In either of these cases we require device map file to be written

            device_map_data = '\n'.join(
                f'(hd{i}) {d.data["attributes"]["path"]}' for i, d in enumerate(filter(
                    lambda d: isinstance(d, RAW) and d.data['attributes'].get('boot'), self.devices
                ))
            )
            # It will be ensured while starting that this VM is capable of starting i.e has boot devices

            os_list.append(create_element(
                'bootloader', attribute_dict={'text': '/usr/local/sbin/grub-bhyve'}
            ))

            device_map_dir = os.path.join('/tmp/grub', self.libvirt_domain_name)
            device_map_file = os.path.join(device_map_dir, 'devices_map')
            os.makedirs(device_map_dir, exist_ok=True)

            with open(device_map_file, 'w') as f:
                f.write(device_map_data)

            if self.vm_data['grubconfig']:
                grub_config = self.vm_data['grubconfig'].strip()
                if grub_config.startswith('/mnt'):
                    grub_dir = os.path.dirname(grub_config)
                else:
                    grub_dir = device_map_dir
                    with open(os.path.join(grub_dir, 'grub.cfg'), 'w') as f:
                        f.write(grub_config)

                os_list.append(create_element(
                    'bootloader_args', attribute_dict={
                        'text': ' '.join([
                            '-m', device_map_file, '-r', 'host', '-M', str(self.vm_data['memory']),
                            '-d', grub_dir, self.libvirt_domain_name
                        ])
                    }
                ))

        os_list.append(create_element('os', attribute_dict={'children': children}))

        return os_list

    def construct_xml(self):
        return create_element(
            'domain', type='bhyve', id=str(self.vm_data['id']),
            attribute_dict={'children': self.get_domain_children()}, nsmap=LIBVIRT_BHYVE_NSMAP,
        )

    def commandline_args(self):
        args = []
        for device in filter(lambda d: isinstance(d, (PCI, DISPLAY)), self.devices):
            args += filter(None, [device.hypervisor_args()])
        return args

    def commandline_xml(self):
        commandline_args = self.commandline_args()
        return [create_element(
            etree.QName(LIBVIRT_BHYVE_NAMESPACE, 'commandline'), attribute_dict={
                'children': [
                    create_element(
                        etree.QName(LIBVIRT_BHYVE_NAMESPACE, 'arg'), value=cmd_arg, nsmap=LIBVIRT_BHYVE_NSMAP
                    ) for cmd_arg in commandline_args
                ]
            }
        )] if commandline_args else []

    def devices_xml(self):
        devices = []
        pci_slot = Nid(3)
        controller_index = Nid(1)
        controller_base = {'index': None, 'slot': None, 'function': 0, 'devices': 0}
        ahci_current_controller = controller_base.copy()
        virtio_current_controller = controller_base.copy()
        ppt_maps = []

        for device in self.devices:
            if isinstance(device, (DISK, CDROM, RAW)):
                # We classify all devices in 2 types:
                # 1) AHCI
                # 2) VIRTIO
                # Before deciding how we attach the disk/cdrom devices wrt slots/functions, following are few basic
                # rules:
                # We have a maximum of 32 slots ( 0-31 ) available which can be attached to the VM. Each slot supports
                # functions which for each slot can be up to 8 ( 0-7 ). For legacy reasons, we start with the 3rd
                # slot for numbering disks.

                # AHCI based devices can be up to 32 in number per function.
                # VIRTIO based disk devices consume a complete function meaning a maximum of 1 VIRTIO device can be
                # present in a function.

                # Libvirt / freebsd specific implementation
                # We do not have great support of bhyve driver in libvirt, so this is a best effort to emulate our
                # old implementation command. Following are a few points i have outlined to make the following logic
                # clearer:
                # 1) For AHCI based devices, libvirt assigns all of them to one slot ( a bug there ), we don't want
                # that of course as bhyve imposes a restriction of a maximum 32 devices per function for AHCI. To come
                # around this issue, controllers have been used for AHCI based devices which help us manage them
                # nicely allotting them on specific supplied slots/functions.
                # 2) For VIRTIO based disk devices, we use "pci" for their address type which helps us set
                # the slot/function number and it actually being respected. Reason this can't be used with AHCI is
                # that pci and sata bus are incompatible in AHCI and libvirt raises an error in this case.

                if device.data['attributes'].get('type') != 'VIRTIO':
                    virtio = False
                    current_controller = ahci_current_controller
                    max_devices = 32
                else:
                    virtio = True
                    current_controller = virtio_current_controller
                    max_devices = 1

                if not current_controller['slot'] or current_controller['devices'] == max_devices:
                    # Two scenarios will happen, either we bump function no or slot no
                    if not current_controller['slot'] or current_controller['function'] == 8:
                        # We need to add a new controller with a new slot
                        current_controller.update({
                            'slot': pci_slot(),
                            'function': 0,
                            'devices': 0,
                        })
                    else:
                        # We just need to bump the function here
                        current_controller.update({
                            'function': current_controller['function'] + 1,
                            'devices': 0,
                        })

                    # We should add this to xml now
                    if not virtio:
                        current_controller['index'] = controller_index()
                        devices.append(create_element(
                            'controller', type='sata', index=str(current_controller['index']), attribute_dict={
                                'children': [
                                    create_element(
                                        'address', type='pci', slot=str(current_controller['slot']),
                                        function=str(current_controller['function']), multifunction='on'
                                    )
                                ]
                            }
                        ))

                current_controller['devices'] += 1

                if virtio:
                    address_dict = {
                        'type': 'pci', 'slot': str(current_controller['slot']),
                        'function': str(current_controller['function'])
                    }
                else:
                    address_dict = {
                        'type': 'drive', 'controller': str(current_controller['index']),
                        'target': str(current_controller['devices'])
                    }

                device_xml = device.xml(child_element=create_element('address', **address_dict))
            elif isinstance(device, NIC):
                device_xml = device.xml(slot=pci_slot())
            elif isinstance(device, PCI):
                # PCI passthru section begins here
                # Check if ppt device is available for passthru. Map, only if available.
                host_bsf = device.ppt_map['host_bsf']
                if host_bsf is not None:
                    guest_bsf = self.guest_pptdev(ppt_maps, pci_slot, host_bsf)
                else:
                    guest_bsf = None
                device.ppt_map['guest_bsf'] = guest_bsf
                if guest_bsf is not None:
                    ppt_maps.append(device.ppt_map)
                device_xml = device.xml()
                # PCI passthru section ends here
            else:
                device_xml = device.xml()

            if device_xml is not None:
                devices.extend(device_xml if isinstance(device_xml, (tuple, list)) else [device_xml])

        devices.append(
            create_element(
                'serial', type='nmdm', attribute_dict={
                    'children': [
                        create_element(
                            'source', master=f'/dev/nmdm{self.vm_data["id"]}A', slave=f'/dev/nmdm{self.vm_data["id"]}B'
                        )
                    ]
                }
            )
        )

        return create_element('devices', attribute_dict={'children': devices})

    def guest_pptdev(self, ppt_maps, nid, host_bsf):

        # Multi-function PCI devices are not always independent. For some (but
        # not all) adapters the mappings of functions must be the same in the
        # guest. For simplicity, we map functions of the same host slot on one
        # guest slot.

        # Compile list of already assigned devices with same source slot
        mylist = (item for item in ppt_maps if item['host_bsf'][0:2] == host_bsf[0:2])
        item = next(mylist, None)
        if item is None:
            # Source bus/slot not seen before. Map on new guest slot.
            guest_slot = nid()
        else:
            # Source bus/slot seen before. Reuse the old guest slot.
            guest_slot = item['guest_bsf'][1]
            # Check if the function has already been mapped.
            # No need to map the same bus/slot/function more than once.
            while (item is not None and item['host_bsf'] != host_bsf):
                # Not same function. Check next item.
                item = next(mylist, None)
        if item is None:
            # This host bus/slot/function is not mapped yet.
            # Add passthru device
            guest_bsf = [0, guest_slot, host_bsf[2]]
            return guest_bsf
        return None

    def before_start_checks(self):
        super().before_start_checks()
        if len([d for d in self.devices if isinstance(d, DISPLAY)]) > 1:
            raise CallError('Only one Display device per VM is supported')
