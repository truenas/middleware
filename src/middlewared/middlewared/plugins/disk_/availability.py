from collections import defaultdict

from middlewared.service import accepts, private, Service
from middlewared.service_exception import ValidationErrors
from middlewared.schema import Bool


class DiskService(Service):

    @private
    async def get_exported_disks(self, info, disks=None):
        disks = set() if disks is None else disks
        if isinstance(info, dict):
            path = info.get('path')
            if path and path.startswith('/dev/'):
                path = path.removeprefix('/dev/')
                if disk := await self.middleware.call('disk.label_to_disk', path):
                    disks.add(disk)

            for key in info:
                await self.get_exported_disks(info[key], disks)
        elif isinstance(info, list):
            for idx, entry in enumerate(info):
                await self.get_exported_disks(info[idx], disks)

        return disks

    @private
    async def get_unused_impl(self):
        in_use_disks_imported = []
        for guid, info in (await self.middleware.call('zfs.pool.query_imported_fast')).items():
            in_use_disks_imported.extend(await self.middleware.call('zfs.pool.get_disks', info['name']))

        in_use_disks_exported = {}
        for i in await self.middleware.call('zfs.pool.find_import'):
            for in_use_disk in await self.get_exported_disks(i['groups']):
                in_use_disks_exported[in_use_disk] = i['name']

        unused = []
        unsupported_md_devices_mapping = await self.middleware.call('disk.get_disks_to_unsupported_md_devices_mapping')
        serial_to_disk = defaultdict(list)
        for i in await self.middleware.call(
            'datastore.query', 'storage.disk', [['disk_expiretime', '=', None]], {'prefix': 'disk_'}
        ):
            if i['name'] in in_use_disks_imported:
                # exclude disks that are currently in use by imported zpool(s)
                continue

            # disk is "technically" not "in use" but the zpool is exported
            # and can be imported so the disk would be "in use" if the zpool
            # was imported so we'll mark this disk specially so that end-user
            # can be warned appropriately
            i['exported_zpool'] = in_use_disks_exported.get(i['name'])
            # User might have unsupported md devices configured and a single disk might have multiple
            # partitions which are being used by different md devices so this value will be a list or null
            i['unsupported_md_devices'] = unsupported_md_devices_mapping.get(i['name'])

            serial_to_disk[(i['serial'], i['lunid'])].append(i)
            unused.append(i)

        for i in unused:
            # need to add a `duplicate_serial` key so that webUI can give an appropriate warning to end-user
            # about disks with duplicate serial numbers (I'm looking at you USB "disks")
            i['duplicate_serial'] = [
                j['name'] for j in serial_to_disk[(i['serial'], i['lunid'])] if j['name'] != i['name']
            ]

            # backwards compatibility
            i['devname'] = i['name']

        return unused

    @accepts(Bool('join_partitions', default=False))
    async def get_unused(self, join_partitions):
        """
        Return disks that are not in use by any zpool that is currently imported. It will
        also return disks that are in use by any zpool that is exported.
        """
        disks = await self.get_unused_impl()

        if join_partitions:
            for disk in disks:
                disk['partitions'] = await self.middleware.call('disk.list_partitions', disk['devname'])

        return disks

    @private
    async def get_reserved(self):
        return await self.middleware.call('boot.get_disks') + await self.middleware.call('pool.get_disks')

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
            serial_to_disk = defaultdict(set)
            for disk in disks:
                serial_to_disk[(disks_cache[disk]['serial'], disks_cache[disk]['lunid'])].add(disk)
            for reserved_disk in disks_reserved:
                reserved_disk_cache = disks_cache.get(reserved_disk)
                if not reserved_disk_cache:
                    continue

                serial_to_disk[(reserved_disk_cache['serial'], reserved_disk_cache['lunid'])].add(reserved_disk)

            if duplicate_serials := {serial for serial, serial_disks in serial_to_disk.items()
                                     if len(serial_disks) > 1}:
                error = ', '.join(map(lambda serial: f'{serial[0]!r} ({", ".join(sorted(serial_to_disk[serial]))})',
                                      duplicate_serials))
                verrors.add('topology', f'Disks have duplicate serial numbers: {error}.')

        return verrors
