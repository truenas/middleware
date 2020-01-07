import json
import re

from middlewared.service import accepts, CallError, private, Service, Str

RE_SATA_DOM_LIFETIME = re.compile(r'^164\s+.*\s+([0-9]+)$', re.M)


class DiskService(Service):
    @accepts(Str('name'))
    async def smart_attributes(self, name):
        """
        Returns S.M.A.R.T. attributes values for specified disk name.
        """
        output = json.loads(await self.middleware.call('disk.smartctl', name, ['-A', '-j']))

        if 'ata_smart_attributes' in output:
            return output['ata_smart_attributes']['table']

        raise CallError('Only ATA device support S.M.A.R.T. attributes')

    @private
    async def sata_dom_lifetime_left(self, name):
        output = await self.middleware.call('disk.smartctl', name, ['-A'], {'silent': True})
        if output is None:
            return None

        m = RE_SATA_DOM_LIFETIME.search(output)
        if m:
            aec = int(m.group(1))
            return max(1.0 - aec / 3000, 0)
