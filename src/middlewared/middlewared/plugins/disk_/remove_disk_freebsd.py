from middlewared.service import private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    async def remove_disk_from_graid(self, dev):
        # Its possible a disk was previously used by graid so we need to make sure to
        # remove the disk from it (#40560)
        gdisk = await self.middleware.call('geom.cache.get_class_xml', 'DISK')
        graid = await self.middleware.call('geom.cache.get_class_xml', 'RAID')
        if (gdisk and graid) and (prov := gdisk.xml.find(f'.//provider[name = "{dev}"]')):
            provid = prov.attrib.get('id')
            if graid := graid.xml.find(f'.//consumer/provider[@ref = "{provid}"]/../../name'):
                cp = await run('graid', 'remove', graid.text, dev, check=False)
                if cp.returncode != 0:
                    self.logger.debug(
                        'Failed to remove %s from %s: %s', dev, graid.text, cp.stderr.decode()
                    )
