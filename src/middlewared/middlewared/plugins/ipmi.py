import os

from middlewared.schema import accepts, returns, Bool
from middlewared.service import Service


class IPMIService(Service):

    class Config:
        cli_namespace = 'system.ipmi'

    @accepts()
    @returns(Bool('ipmi_loaded'))
    def is_loaded(self):
        """Returns a boolean value indicating if /dev/ipmi0 is loaded."""
        return os.path.exists('/dev/ipmi0')


async def setup(middleware):
    if await middleware.call('system.ready') and (await middleware.call('system.dmidecode_info'))['has-ipmi']:
        # systemd generates a unit file that doesn't honor presets so when it's started on a system without a
        # BMC device, it always reports as a failure which is expected since no IPMI device exists. Instead
        # we check to see if dmidecode reports an ipmi device via type "38" of the SMBIOS spec. It's not
        # fool-proof but it's the best we got atm.
        await middleware.call('service.start', 'openipmi')
