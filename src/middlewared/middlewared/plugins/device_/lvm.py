from collections import defaultdict

from middlewared.service import CallError, private, Service
from middlewared.utils import run


class DeviceService(Service):

    @private
    async def list_lvm_to_disk_mapping(self):
        cp = await run(
            ['pvs', '--separator', ';', '-o', 'pv_name,lv_name,vg_name', '--noheadings'],
            check=False, encoding='utf8', errors='ignore'
        )
        if cp.returncode:
            raise CallError(f'Failed to get LVM to disk mapping: {cp.stderr}', errno=cp.returncode)

        mapping = defaultdict(list)
        for entry in filter(bool, cp.stdout.splitlines()):
            data = list(filter(bool, map(str.strip, entry.split(';'))))
            if len(data) != 3:
                continue

            pv_name, lv_name, vg_name = data
            mapping[
                await self.middleware.call('disk.normalize_device_to_disk_name', pv_name.removeprefix('/dev/'))
            ].append((vg_name, lv_name))

        return mapping
