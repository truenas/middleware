from middlewared.schema import accepts, Str
from middlewared.service import Service

from bsd import devinfo


class DeviceService(Service):

    @accepts(Str('type', enum=['SERIAL']))
    def get_info(self, _type):
        """
        Get info for certain device types.

        Currently only SERIAL is supported.
        """
        return getattr(self, f'_get_{_type.lower()}')()

    def _get_serial(self):
        ports = []
        for devices in devinfo.DevInfo().resource_managers['I/O ports'].values():
            for dev in devices:
                if not dev.name.startswith('uart'):
                    continue
                ports.append({
                    'name': dev.name,
                    'description': dev.desc,
                    'drivername': dev.drivername,
                    'location': dev.location,
                    'start': hex(dev.start),
                    'size': dev.size
                })
        return ports
