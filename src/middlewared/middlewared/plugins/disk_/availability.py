from collections import defaultdict

from middlewared.service import accepts, private, Service
from middlewared.service_exception import ValidationErrors
from middlewared.schema import Bool


class DiskService(Service):
    @accepts(Bool('join_partitions', default=False))
    async def get_unused(self, join_partitions):
        """
        Helper method to get all disks that are not in use, either by the boot
        pool or the user pools.
        """
        all_disks = await self.middleware.call('disk.query')

        serial_to_disk = defaultdict(list)
        for disk in all_disks:
            serial_to_disk[(disk['serial'], disk['lunid'])].append(disk)

        reserved = await self.middleware.call('disk.get_reserved')
        disks = [disk for disk in all_disks if disk['devname'] not in reserved]

        for disk in disks:
            disk['duplicate_serial'] = [
                d['devname']
                for d in serial_to_disk[(disk['serial'], disk['lunid'])]
                if d['devname'] != disk['devname']
            ]

        if join_partitions and disks:
            part_xml = await self.middleware.call('disk.get_part_xml')
            if not part_xml:
                return disks

            for disk in disks:
                disk['partitions'] = await self.middleware.call('disk.list_partitions', disk['devname'], part_xml)

        return disks

    @private
    async def get_reserved(self):
        reserved = list(await self.middleware.call('boot.get_disks'))
        reserved += [i async for i in await self.middleware.call('pool.get_disks')]
        reserved += [i async for i in self.__get_iscsi_targets()]
        return reserved

    async def __get_iscsi_targets(self):
        iscsi_target_extent_paths = [
            extent['iscsi_target_extent_path']
            for extent in await self.middleware.call('datastore.query', 'services.iscsitargetextent',
                                                     [('iscsi_target_extent_type', '=', 'Disk')])
        ]
        for disk in await self.middleware.call('datastore.query', 'storage.disk',
                                               [('disk_identifier', 'in', iscsi_target_extent_paths)]):
            yield disk['disk_name']

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
                serial_to_disk[(disks_cache[disk]['serial'], disks_cache[disk]['lunid'])].append(disk)
            for reserved_disk in disks_reserved:
                reserved_disk_cache = disks_cache.get(reserved_disk)
                if not reserved_disk_cache:
                    continue

                serial_to_disk[(reserved_disk_cache['serial'], reserved_disk_cache['lunid'])].append(reserved_disk)

            if duplicate_serials := {serial for serial, serial_disks in serial_to_disk.items()
                                     if len(serial_disks) > 1}:
                error = ', '.join(map(lambda serial: f'{serial[0]!r} ({", ".join(serial_to_disk[serial])})',
                                      duplicate_serials))
                verrors.add('topology', f'Disks have duplicate serial numbers: {error}.')

        disks_cache = {k: v for k, v in disks_cache.items() if k in disks}

        return verrors, disks_cache
