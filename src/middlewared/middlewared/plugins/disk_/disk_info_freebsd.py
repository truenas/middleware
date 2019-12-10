import re

from bsd import geom

from middlewared.service import Service
from middlewared.utils import run

from .disk_info_base import DiskInfoBase


class DiskService(Service, DiskInfoBase):

    async def get_dev_size(self, dev):
        cp = await run('diskinfo', dev)
        if not cp.returncode:
            return int(int(re.sub(r'\s+', ' ', cp.stdout.decode()).split()[2]))

    def list_partitions(self, disk):
        geom.scan()
        klass = geom.class_by_name('PART')
        parts = []
        for g in klass.xml.findall(f'./geom[name=\'{disk}\']'):
            for p in g.findall('./provider'):
                size = p.find('./mediasize')
                if size is not None:
                    try:
                        size = int(size.text)
                    except ValueError:
                        size = None
                name = p.find('./name')
                parts.append({'name': name.text, 'size': size})

        return parts
