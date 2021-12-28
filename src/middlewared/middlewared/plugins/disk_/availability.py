from collections import defaultdict

from middlewared.service import private, Service
from middlewared.service_exception import ValidationErrors


class DiskService(Service):
    @private
    async def check_disks_availability(self, disks, allow_duplicate_serials):
        """
        Makes sure the disks are present in the system and not reserved
        by anything else (boot, pool, iscsi, etc).

        Returns:
            verrors, dict - validation errors (if any) and disk.query for all disks
        """
        verrors = ValidationErrors()
        disks_cache = dict(map(lambda x: (x['devname'], x), await self.middleware.call('disk.query')))

        disks_set = set(disks)
        disks_not_in_cache = disks_set - set(disks_cache.keys())
        if disks_not_in_cache:
            verrors.add(
                'topology',
                f'The following disks were not found in system: {"," .join(disks_not_in_cache)}.'
            )

        disks_reserved = await self.middleware.call('disk.get_reserved')
        already_used = disks_set - (disks_set - set(disks_reserved))
        if already_used:
            verrors.add(
                'topology',
                f'The following disks are already in use: {"," .join(already_used)}.'
            )

        if not allow_duplicate_serials and not verrors:
            serial_to_disk = defaultdict(list)
            for disk in disks:
                serial_to_disk[disks_cache[disk]['serial']].append(disk)
            for reserved_disk in disks_reserved:
                reserved_disk_cache = disks_cache.get(reserved_disk)
                if not reserved_disk_cache:
                    continue

                serial_to_disk[reserved_disk_cache['serial']].append(reserved_disk)

            if duplicate_serials := {serial for serial, serial_disks in serial_to_disk.items()
                                     if len(serial_disks) > 1}:
                error = ', '.join(map(lambda serial: f'{serial!r} ({", ".join(serial_to_disk[serial])})',
                                      duplicate_serials))
                verrors.add('topology', f'Disks have duplicate serial numbers: {error}.')

        disks_cache = {k: v for k, v in disks_cache.items() if k in disks}

        return verrors, disks_cache
