import errno
import os

from middlewared.schema import Str
from middlewared.service import accepts, CallError, private, returns, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def update_volumes_for_release(self, release, volumes):
        ix_volumes_ds = os.path.join(release['dataset'], 'volumes/ix_volumes')
        existing_datasets = {
            d['id'] for d in await self.middleware.call(
                'zfs.dataset.query', [['id', '^', f'{ix_volumes_ds}/']], {'extra': {'retrieve_properties': False}}
            )
        }
        user_wants = {os.path.join(ix_volumes_ds, v['name']): v for v in volumes}

        for create_ds in set(user_wants) - existing_datasets:
            await self.middleware.call(
                'zfs.dataset.create', {
                    'properties': user_wants[create_ds]['properties'], 'name': create_ds, 'type': 'FILESYSTEM'
                }
            )
            await self.middleware.call('zfs.dataset.mount', create_ds)

    @accepts(
        Str('release_name'),
        Str('volume_name'),
    )
    @returns()
    async def remove_ix_volume(self, release_name, volume_name):
        """
        Remove `volume_name` ix_volume from `release_name` chart release.
        """
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )

        volume_ds = os.path.join(release['dataset'], 'volumes/ix_volumes', volume_name)
        if not await self.middleware.call('zfs.dataset.query', [['id', '=', volume_ds]]):
            raise CallError(f'Unable to locate {volume_name!r} volume', errno=errno.ENOENT)

        used_host_path_volumes = {v['host_path'].get('path', '') for v in release['resources']['host_path_volumes']}
        if os.path.join('/mnt', volume_ds) in used_host_path_volumes:
            raise CallError(
                f'{volume_name!r} is configured as a host path volume for a workload, please remove it from workload'
            )

        # Now it's safe to delete the dataset
        await self.middleware.call('zfs.dataset.delete', volume_ds, {'force': True, 'recursive': True})
