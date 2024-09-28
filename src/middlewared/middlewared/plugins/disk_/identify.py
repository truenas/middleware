import re

from middlewared.schema import accepts, Dict, Str
from middlewared.service import Service, private
from middlewared.utils.disks import get_disks_with_identifiers


class DiskService(Service):

    RE_IDENTIFIER = re.compile(r'^\{(?P<type>.+?)\}(?P<value>.+)$')

    @private
    @accepts(Str('name'), Dict('disks', additional_attrs=True))
    def device_to_identifier(self, name, disks):
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
        return get_disks_with_identifiers([name], disks).get(name, '')

    @private
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
