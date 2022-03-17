import pyudev
import re

from middlewared.schema import accepts, Dict, Str
from middlewared.service import Service, private


class DiskService(Service):

    RE_IDENTIFIER = re.compile(r'^\{(?P<type>.+?)\}(?P<value>.+)$')

    @private
    @accepts(Str('name'), Dict('disks', additional_attrs=True))
    async def device_to_identifier(self, name, disks):
        """
        Given a device `name` (e.g. sda) returns an unique identifier string
        for this device.
        This identifier is in the form of {type}string, "type" can be one of
        the following:
          - serial_lunid - for disk serial concatenated with the lunid
          - serial - disk serial
          - uuid - uuid of a ZFS GPT partition
          - label - label name from geom label
          - devicename - name of the device if any other could not be used/found

        `disks` is value returned by `device.get_disks`. This can be passed to avoid collecting system
        data again if the consumer already has it.
        Returns:
            str - identifier
        """
        disks = disks or await self.middleware.call('device.get_disks')
        if name not in disks:
            return ''
        else:
            block_device = disks[name]

        if block_device['serial_lunid']:
            return f'{{serial_lunid}}{block_device["serial_lunid"]}'
        elif block_device['serial']:
            return f'{{serial}}{block_device["serial"]}'

        dev = pyudev.Devices.from_name(pyudev.Context(), 'block', name)
        for partition in filter(
            lambda p: all(p.get(k) for k in ('ID_PART_ENTRY_TYPE', 'ID_PART_ENTRY_UUID')), dev.children
        ):
            if partition['ID_PART_ENTRY_TYPE'] not in await self.middleware.call(
                'disk.get_valid_zfs_partition_type_uuids'
            ):
                continue
            return f'{{uuid}}{partition["ID_PART_ENTRY_UUID"]}'

        return f'{{devicename}}{name}'

    async def identifier_to_device(self, ident, disks):
        if not ident:
            return None

        search = self.RE_IDENTIFIER.search(ident)
        if not search:
            return None

        tp = search.group('type')
        value = search.group('value')
        mapping = {'uuid': 'uuid', 'devicename': 'name', 'serial_lunid': 'serial_lunid', 'serial': 'serial'}
        if tp not in mapping:
            return None
        elif tp == 'uuid':
            partition = await self.middleware.call('disk.list_all_partitions', [['partition_uuid', '=', value]])
            if partition:
                return partition[0]['disk']
        else:
            disk = next(
                (b for b in (
                    disks or await self.middleware.call('device.get_disks')
                ).values() if b[mapping[tp]] == value), None
            )
            return disk['name'] if disk else None
