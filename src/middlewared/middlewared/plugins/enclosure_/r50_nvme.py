from pyudev import Context, Devices, DeviceNotFoundAtPathError

from middlewared.service import Service, private


class EnclosureService(Service):

    @private
    def map_nvme(self, info, acpihandles):
        mapped = info[-1]
        num_of_nvme_slots = info[-2]
        ctx = Context()
        for i in filter(lambda x: (x.attributes.get('path') or '') in acpihandles, ctx.list_devices(subsystem='acpi')):
            acpi_handle = i.attributes.get('path')
            try:
                phys_node = Devices.from_path(ctx, f'{i.sys_path}/physical_node')
            except DeviceNotFoundAtPathError:
                return info

            slot = acpihandles[acpi_handle]
            for nvme in filter(lambda x: x.sys_name.startswith('nvme'), phys_node.children):
                mapped[slot] = nvme.sys_name
                break
            else:
                mapped[slot] = None

            if len(mapped) == num_of_nvme_slots:
                # means we've checked all the acpi handles for the the nvme drives
                # so instead of continually iterating every acpi device on
                # the system return early
                return info

        return info

    @private
    def r50_nvme_enclosures(self):
        prod = self.middleware.call_sync('system.dmidecode_info')['system-product-name']
        if prod not in ('TRUENAS-R50', 'TRUENAS-R50B'):
            return []

        if prod == 'TRUENAS-R50':
            info = [
                'r50_nvme_enclosure',
                'R50 NVMe Enclosure',
                'R50, Drawer #3',
                3,  # r50 has 3 rear nvme
                {},
            ]
            acpihandles = {b'\\_SB_.PC00.RP01.PXSX': 3, b'\\_SB_.PC01.BR1A.OCL0': 1, b'\\_SB_.PC01.BR1B.OCL1': 2}
        else:
            info = [
                'r50b_nvme_enclosure',
                'R50B NVMe Enclosure',
                'R50B, Drawer #3',
                2,  # r50b has 2 rear nvme
                {},
            ]
            acpihandles = {b'\\_SB_.PC03.BR3A': 2, b'\\_SB_.PC00.RP01.PXSX': 1}

        return self.middleware.call_sync('enclosure.fake_nvme_enclosure', *self.map_nvme(info, acpihandles))
