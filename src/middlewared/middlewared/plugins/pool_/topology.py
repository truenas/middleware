from collections import deque

from middlewared.service import Service, private

from .utils import RE_DRAID_DATA_DISKS, RE_DRAID_NAME, RE_DRAID_SPARE_DISKS


def _transform_stats(stats):
    """Transform new pylibzfs vdev stats dict to legacy libzfs format.

    Legacy stats keys: timestamp, read_errors, write_errors, checksum_errors,
    ops (7-element array), bytes (7-element array), size, allocated,
    fragmentation, self_healed, configured_ashift, logical_ashift, physical_ashift.
    """
    return {
        'timestamp': stats.get('timestamp', 0),
        'read_errors': stats.get('read_errors', 0),
        'write_errors': stats.get('write_errors', 0),
        'checksum_errors': stats.get('checksum_errors', 0),
        'ops': [0, stats.get('ops_read', 0), stats.get('ops_write', 0), 0, 0, 0, 0],
        'bytes': [0, stats.get('bytes_read', 0), stats.get('bytes_write', 0), 0, 0, 0, 0],
        'size': stats.get('space', 0),
        'allocated': stats.get('allocated', 0),
        'fragmentation': stats.get('fragmentation', 0),
        'self_healed': stats.get('self_healed_bytes', 0),
        'configured_ashift': stats.get('configured_ashift', 0),
        'logical_ashift': stats.get('logical_ashift', 0),
        'physical_ashift': stats.get('physical_ashift', 0),
    }


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
        Transform topology output from zpool.query_impl to add `device`, `disk`,
        `path`, `status`, `type` (uppercase), and `unavail_disk` fields.

        Also converts vdev stats and guid to legacy format.
        """
        options = options or {}
        if isinstance(x, dict):
            # Rename pylibzfs field names to legacy names
            if 'vdev_type' in x:
                vtype = x.pop('vdev_type')
                # Normalize draid config strings (e.g. 'draid1:1d:2c:0s') to
                # plain 'draid' to match the legacy py-libzfs behavior. The
                # parity/config is extracted from the vdev name separately.
                if vtype.startswith('draid'):
                    vtype = 'draid'
                x['type'] = vtype
            if 'state' in x and 'status' not in x:
                state = x.pop('state')
                x['status'] = 'UNAVAIL' if state == 'CANT_OPEN' else state
            if 'spares' in x:
                x['spare'] = x.pop('spares')

            # Remove internal fields
            x.pop('top_guid', None)

            # Merge stripe vdevs into data for legacy format
            if 'stripe' in x:
                x['data'].extend(x.pop('stripe'))

            # Convert vdev stats to legacy format
            if 'stats' in x and isinstance(x['stats'], dict):
                x['stats'] = _transform_stats(x['stats'])

            # Convert guid to string for legacy compatibility
            if 'guid' in x and not isinstance(x['guid'], str):
                x['guid'] = str(x['guid'])

            # Add path for leaf vdevs
            if 'path' not in x and 'name' in x:
                x['path'] = x['name'] if x['name'].startswith('/dev/') else None

            if options.get('device_disk', True):
                path = x.get('path')
                if path is not None and 'device' not in x:
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
        elif isinstance(x, (list, tuple)):
            if isinstance(x, tuple):
                x = list(x)
            for i, entry in enumerate(x):
                x[i] = self.transform_topology(x[i], dict(options, geom_scan=False))
        return x
