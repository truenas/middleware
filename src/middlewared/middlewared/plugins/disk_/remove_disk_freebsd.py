from bsd import geom

from middlewared.service import private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    async def remove_disk_from_graid(self, dev):
        # Its possible a disk was previously used by graid so we need to make sure to
        # remove the disk from it (#40560)
        gdisk = geom.class_by_name('DISK')
        graid = geom.class_by_name('RAID')
        if gdisk and graid:
            prov = gdisk.xml.find(f'.//provider[name = "{dev}"]')
            if prov is not None:
                provid = prov.attrib.get('id')
                graid = graid.xml.find(f'.//consumer/provider[@ref = "{provid}"]/../../name')
                if graid is not None:
                    cp = await run('graid', 'remove', graid.text, dev, check=False)
                    if cp.returncode != 0:
                        self.logger.debug(
                            'Failed to remove %s from %s: %s', dev, graid.text, cp.stderr.decode()
                        )
