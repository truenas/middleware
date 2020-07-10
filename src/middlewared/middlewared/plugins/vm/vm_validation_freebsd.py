import math

from middlewared.service import private, Service


class VMService(Service):

    @private
    async def available_slots(self):
        return 29  # 3 slots are being used by libvirt / bhyve

    @private
    async def validate_slots(self, vm_data):
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

        # 3 slots are already in use i.e by libvirt/bhyve
        return not (used_slots > (await self.middleware.call('vm.available_slots')))
