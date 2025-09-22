import logging
import os

from middlewared.api import api_method
from middlewared.api.current import PoolExpandArgs, PoolExpandResult
from middlewared.service import item_method, job, private, Service
from middlewared.utils import run


logger = logging.getLogger(__name__)


class PoolService(Service):

    @item_method
    @api_method(PoolExpandArgs, PoolExpandResult, roles=['POOL_WRITE'])
    @job(lock='pool_expand')
    async def expand(self, job, id_):
        """
        Expand pool to fit all available disk space.
        """
        pool = await self.middleware.call('pool.get_instance', id_)
        vdevs = []
        for vdev in sum(pool['topology'].values(), []):
            if vdev['status'] != 'ONLINE':
                logger.debug('Not expanding vdev(%r) that is %r', vdev['guid'], vdev['status'])
                continue

            c_vdevs = []
            disks = vdev['children'] if vdev['type'] != 'DISK' else [vdev]
            skip_vdev = None
            for child in disks:
                if child['status'] != 'ONLINE':
                    skip_vdev = f'Device "{child["device"]}" status is not ONLINE ' \
                                f'(Reported status is {child["status"]})'
                    break

                disk_info = await self.middleware.call('device.get_disk', child['disk'], True)
                partitions = {p['name']: p for p in (disk_info['parts'] if disk_info else [])}
                part_data = partitions.get(child['device'])
                if not part_data:
                    skip_vdev = f'Unable to find partition data for {child["device"]}'
                elif not part_data['partition_number']:
                    skip_vdev = f'Could not parse partition number from {child["device"]}'
                elif part_data['disk'] != child['disk']:
                    skip_vdev = f'Retrieved partition data for device {child["device"]} ' \
                                f'({part_data["disk"]}) does not match with disk ' \
                                f'reported by ZFS ({child["disk"]})'
                if skip_vdev:
                    break
                else:
                    c_vdevs.append((child['guid'], part_data))

            if skip_vdev:
                logger.debug('Not expanding vdev(%r): %r', vdev['guid'], skip_vdev)
                continue

            for guid, part_data in c_vdevs:
                await self.expand_partition(part_data)
                vdevs.append(guid)

        # spare/cache devices cannot be expanded
        # We resize them anyway, for cache devices, whenever we are going to import the pool
        # next, it will register the new capacity. For spares, whenever that spare is going to
        # be used, it will register the new capacity as desired.
        for topology_type in filter(
            lambda t: t not in ('spare', 'cache') and pool['topology'][t], pool['topology']
        ):
            for vdev in pool['topology'][topology_type]:
                for c_vd in filter(
                    lambda v: v['guid'] in vdevs, vdev['children'] if vdev['type'] != 'DISK' else [vdev]
                ):
                    await self.middleware.call('zfs.pool.online', pool['name'], c_vd['guid'], True)

    @private
    async def expand_partition(self, part_data):
        size = await self.middleware.call('disk.get_data_partition_size', part_data['disk'], part_data['start'])
        if size <= part_data['size']:
            return

        # Wipe potential conflicting ZFS label
        wipe_size = 1024 ** 2
        wipe_start = part_data['start'] + size - wipe_size
        if wipe_start < part_data['end']:
            return

        def wipe_label():
            with open(os.path.join('/dev', part_data['disk']), 'r+b') as f:
                f.seek(wipe_start)
                f.write(b'0' * wipe_size)

        await self.middleware.run_in_thread(wipe_label)

        partition_number = part_data['partition_number']
        start = part_data['start_sector']
        await run(
            'sgdisk', '-d', str(partition_number), '-n', f'{partition_number}:{start}:+{int(size / 1024)}KiB', '-t',
            f'{partition_number}:BF01', '-u', f'{partition_number}:{part_data["partition_uuid"]}',
            os.path.join('/dev', part_data['disk'])
        )
        await run('partprobe', os.path.join('/dev', part_data['disk']))
