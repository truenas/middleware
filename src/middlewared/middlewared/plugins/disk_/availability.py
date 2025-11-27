from collections import defaultdict

from middlewared.api import api_method
from middlewared.api.current import (
    DiskDetailsArgs,
    DiskDetailsResult,
    DiskGetUsedArgs,
    DiskGetUsedResult,
)
from middlewared.service import private, Service
from middlewared.service_exception import ValidationErrors
from middlewared.utils.disks import dev_to_ident


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
    async def details_impl(self, data):
        # see `self.details` for arguments and their meaning
        db_disks = {
            disk['name']: disk for disk in await self.middleware.call('disk.query', [], {'extra': {'sed_status': True}})
        }
        in_use_disks_imported = {}
        for in_use_disk, info in (
            await self.middleware.call('zpool.status', {'real_paths': True})
        )['disks'].items():
            in_use_disks_imported[in_use_disk] = info['pool_name']

        in_use_disks_exported = {}
        for i in await self.middleware.call('zfs.pool.find_import'):
            for in_use_disk in await self.get_exported_disks(i['groups']):
                in_use_disks_exported[in_use_disk] = i['name']

        enc_info = dict()
        for enc in await self.middleware.call('enclosure2.query'):
            for slot, info in filter(lambda x: x[1], enc['elements']['Array Device Slot'].items()):
                enc_info[info['dev']] = (int(slot), enc['id'])

        used, unused = [], []
        serial_to_disk = defaultdict(list)
        sys_disks = await self.middleware.call('device.get_disks')
        for dname, i in sys_disks.items():
            if not i['size']:
                # seen on an internal system during QA. The disk had actually been spun down
                # by OS because it had so many errors so the size was an empty string in our db
                # SMART data reported the following for the disk: "device is NOT READY (e.g. spun down, busy)"
                continue

            i['identifier'] = dev_to_ident(dname, sys_disks)
            i['enclosure_slot'] = enc_info.get(dname, ())
            serial_to_disk[(i['serial'], i['lunid'])].append(i)

            # add enclosure information
            i['enclosure'] = {}
            if enc := i.pop('enclosure_slot'):
                i['enclosure'].update({'drive_bay_number': enc[0], 'id': enc[1]})

            # query partitions for the disk(s) if requested
            i['partitions'] = []
            if data['join_partitions']:
                i['partitions'] = await self.middleware.call('disk.list_partitions', i['name'])

            db_disk = db_disks.get(i['name'], {})  # Should always be there but better safe then sorry
            i.update({
                'sed': db_disk.get('sed'),
                'sed_status': db_disk.get('sed_status'),
            })

            # TODO: UI needs to remove dependency on `devname` since `name` is sufficient
            i['devname'] = i['name']
            try:
                i['size'] = int(i['size'])
            except ValueError:
                i['size'] = None

            # disk is "technically" not "in use" but the zpool is exported
            # and can be imported so the disk would be "in use" if the zpool
            # was imported so we'll mark this disk specially so that end-user
            # can be warned appropriately
            i['exported_zpool'] = in_use_disks_exported.get(dname)

            # disk is in use by a zpool that is currently imported
            i['imported_zpool'] = in_use_disks_imported.get(dname)

            if any((
                i['imported_zpool'] is not None,
                i['exported_zpool'] is not None,
            )):
                used.append(i)
            else:
                unused.append(i)

        for i in used + unused:
            # need to add a `duplicate_serial` key so that webUI can give an appropriate warning to end-user
            # about disks with duplicate serial numbers (I'm looking at you USB "disks")
            i['duplicate_serial'] = [
                j['name'] for j in serial_to_disk[(i['serial'], i['lunid'])] if j['name'] != i['name']
            ]

        return {'used': used, 'unused': unused}

    @private
    async def get_unused(self, join_partitions=False):
        """
        Return disks that are NOT in use by any zpool that is currently imported OR exported.

        `join_partitions`: Bool, when True will return all partitions currently written to disk
            NOTE: this is an expensive operation
        """
        return (await self.details_impl({'join_partitions': join_partitions}))['unused']

    @api_method(DiskGetUsedArgs, DiskGetUsedResult, roles=['REPORTING_READ'])
    async def get_used(self, join_partitions):
        """
        Return disks that are in use by any zpool that is currently imported. It will
        also return disks that are in use by any zpool that is exported.

        `join_partitions`: Bool, when True will return all partitions currently written to disk
            NOTE: this is an expensive operation
        """
        return (await self.details_impl({'join_partitions': join_partitions}))['used']

    @api_method(
        DiskDetailsArgs,
        DiskDetailsResult,
        roles=['REPORTING_READ'],
    )
    async def details(self, data):
        """Return detailed information for all disks on the system."""
        results = await self.details_impl(data)
        if data['type'] == 'BOTH':
            return results
        else:
            return results[data['type'].lower()]

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
        disks_cache = dict()
        for i in await self.middleware.call('disk.get_disks'):
            disks_cache[i.name] = {'serial': i.serial, 'lunid': i.lunid}

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
