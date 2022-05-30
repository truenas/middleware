from pyudev import Context, Devices, DeviceNotFoundByNameError

from middlewared.service import Service, private


class EnclosureService(Service):

    @private
    def map_r50(self, ctx):
        info = [
            'r50_nvme_enclosure',
            'R50 NVMe Enclosure',
            'R50, Drawer #3',
            3,  # r50 has 3 rear nvme
            {},
        ]
        return info

    @private
    def map_r50b(self, ctx):
        info = [
            'r50b_nvme_enclosure',
            'R50B NVMe Enclosure',
            'R50B, Drawer #3',
            2,  # r50b has 2 rear nvme
            {},
        ]
        acpi_handles = (b'\\_SB_.PC03.BR3A', b'\\_SB_.PC00.RP01.PXSX')
        mapped = info[-1]
        num_of_nvme_slots = info[-2]

        for i in ctx.list_devices(subsystem='acpi'):
            if (path := i.attributes.get('path')) and path in acpi_handles:
                try:
                    phys_node = Devices.from_path(ctx, i.sys_path + '/physical_node')
                except DeviceNotFoundByNameError:
                    self.logger.error('Failed to find pci slot information')
                    return info

                if path == b'\\_SB_.PC00.RP01.PXSX':
                    slot = 1
                    dev = next(phys_node.children, None)
                    mapped[slot] = dev.sys_name if dev else None
                elif path == b'\\_SB_.PC03.BR3A':
                    slot = 2
                    for child in phys_node.children:
                        if 'nvme' in child.sys_name:
                            mapped[slot] = child.sys_name
                            break

                if len(mapped) == num_of_nvme_slots:
                    # means we've found the nvme drives that we're searching for
                    # so instead of continually iterating every acpi device on
                    # the system return early
                    return info

        return info

    @private
    def r50_nvme_enclosures(self):
        prod = self.middleware.call_sync('system.dmidecode_info')['system-product-name']
        if prod not in ('TRUENAS-R50', 'TRUENAS-R50B'):
            return []

        ctx = Context()
        method = self.map_r50 if prod == 'TRUENAS-R50' else self.map_r50b
        return self.middleware.call_sync('enclosure.fake_nvme_enclosure', *method(ctx))
