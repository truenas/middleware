from middlewared.service import Service, private
from middlewared.utils.disks import get_disks_with_identifiers


class DiskService(Service):

    @private
    def device_to_identifier(self, name: str, disks: dict):
        """
        Given a device `name` (e.g. sda) returns an unique identifier string
        for this device.
        This identifier is in the form of {type}string, "type" can be one of
        the following:
          - serial_lunid - for disk serial concatenated with the lunid
          - serial - disk serial
          - uuid - uuid of a ZFS GPT partition
          - devicename - name of the device if any other could not be used/found

        `disks` is value returned by `device.get_disks`. This can be passed to avoid collecting system
        data again if the consumer already has it.
        Returns:
            str - identifier
        """
        return get_disks_with_identifiers([name], disks).get(name, '')
