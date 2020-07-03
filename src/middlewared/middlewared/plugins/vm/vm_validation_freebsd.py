import math

from middlewared.service import Service

from .vm_validation_base import VMValidationBase


LIBVIRT_AVAILABLE_SLOTS = 29  # 3 slots are being used by libvirt / bhyve


class VMService(Service, VMValidationBase):

    def validate_slots(self, vm_data):
        virtio_disk_devices = raw_ahci_disk_devices = other_devices = 0
        for device in (vm_data.get('devices') or []):
            if device['dtype'] not in ('DISK', 'RAW'):
                other_devices += 1
            else:
                if device['attributes'].get('type') == 'VIRTIO':
                    virtio_disk_devices += 1
                else:
                    raw_ahci_disk_devices += 1
        used_slots = other_devices
        used_slots += math.ceil(virtio_disk_devices / 8)  # Per slot we can have 8 virtio disks, so we divide it by 8
        # Per slot we can have 256 disks.
        used_slots += math.ceil(raw_ahci_disk_devices / 256)
        return used_slots > LIBVIRT_AVAILABLE_SLOTS  # 3 slots are already in use i.e by libvirt/bhyve

    def validate_vcpus(self, vcpus, schema_name, verrors):
        flags = await self.middleware.call('vm.flags')
        if vcpus > 16:
            verrors.add(
                f'{schema_name}.vcpus',
                'Maximum 16 vcpus are supported.'
                f'Please ensure the product of "{schema_name}.vcpus", "{schema_name}.cores" and '
                f'"{schema_name}.threads" is less then 16.'
            )
        elif flags['intel_vmx']:
            if vcpus > 1 and flags['unrestricted_guest'] is False:
                verrors.add(f'{schema_name}.vcpus', 'Only one Virtual CPU is allowed in this system.')
        elif flags['amd_rvi']:
            if vcpus > 1 and flags['amd_asids'] is False:
                verrors.add(
                    f'{schema_name}.vcpus', 'Only one virtual CPU is allowed in this system.'
                )
        elif not flags['intel_vmx'] and not flags['amd_rvi']:
            verrors.add(schema_name, 'This system does not support virtualization.')
