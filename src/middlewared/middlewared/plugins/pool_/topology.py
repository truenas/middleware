from collections import deque

from middlewared.service import private, Service
from .utils import RE_DRAID_SPARE_DISKS, RE_DRAID_DATA_DISKS, RE_DRAID_NAME


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @private
    def flatten_topology(self, topology):
        d = deque(sum(topology.values(), []))
        result = []
        while d:
            vdev = d.popleft()
            result.append(vdev)
            d.extend(vdev['children'])
        return result

    @private
    async def transform_topology_lightweight(self, x):
        return await self.middleware.call('pool.transform_topology', x, {'device_disk': False, 'unavail_disk': False})

    @private
    def transform_topology(self, x, options=None):
        """
        Transform topology output from libzfs to add `device` and make `type` uppercase.
        """
        options = options or {}
        if isinstance(x, dict):
            if options.get('device_disk', True):
                path = x.get('path')
                if path is not None:
                    device = disk = None
                    if path.startswith('/dev/'):
                        args = [path[5:]]
                        device = self.middleware.call_sync('disk.label_to_dev', *args)
                        disk = self.middleware.call_sync('disk.label_to_disk', *args)
                    x['device'] = device
                    x['disk'] = disk

            if options.get('unavail_disk', True):
                guid = x.get('guid')
                if guid is not None:
                    unavail_disk = None
                    if x.get('status') != 'ONLINE':
                        unavail_disk = self.middleware.call_sync('disk.disk_by_zfs_guid', guid)
                    x['unavail_disk'] = unavail_disk

            for key in x:
                if key == 'type' and isinstance(x[key], str):
                    x[key] = x[key].upper()
                elif key == 'name' and RE_DRAID_NAME.match(x[key]) and isinstance(x.get('stats'), dict):
                    x['stats'].update({
                        'draid_spare_disks': int(RE_DRAID_SPARE_DISKS.findall(x['name'])[0][1:-1]),
                        'draid_data_disks': int(RE_DRAID_DATA_DISKS.findall(x['name'])[0][1:-1]),
                        'draid_parity': int(x['name'][len('draid'):len('draid') + 1]),
                    })
                else:
                    x[key] = self.transform_topology(x[key], dict(options, geom_scan=False))
        elif isinstance(x, list):
            for i, entry in enumerate(x):
                x[i] = self.transform_topology(x[i], dict(options, geom_scan=False))
        return x
