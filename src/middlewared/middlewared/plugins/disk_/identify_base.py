import re

from middlewared.schema import accepts, Str
from middlewared.service import private, ServicePartBase


class DiskIdentifyBase(ServicePartBase):

    RE_IDENTIFIER = re.compile(r'^\{(?P<type>.+?)\}(?P<value>.+)$')

    @private
    @accepts(Str('name'))
    async def device_to_identifier(self, name):
        """
        Given a device `name` (e.g. da0) returns an unique identifier string
        for this device.
        This identifier is in the form of {type}string, "type" can be one of
        the following:
          - serial_lunid - for disk serial concatenated with the lunid
          - serial - disk serial
          - uuid - uuid of a ZFS GPT partition
          - label - label name from geom label
          - devicename - name of the device if any other could not be used/found

        Returns:
            str - identifier
        """

    @private
    @accepts(Str('identifier'))
    def identifier_to_device(self, ident):
        raise NotImplementedError()
