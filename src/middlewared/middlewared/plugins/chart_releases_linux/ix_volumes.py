import os

from middlewared.service import private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def update_volumes_for_release(self, release, volumes):
        ix_volumes_ds = os.path.join(release['dataset'], 'volumes/ix_volumes')
        existing_datasets = {
            d['id'] for d in await self.middleware.call('zfs.dataset.query', [['id', '^', f'{ix_volumes_ds}/']])
        }
        user_wants = {v for v in volumes}
        for remove_ds in existing_datasets - user_wants:
            await self.middleware.call('zfs.dataset.delete', remove_ds, {'force': True})

        for create_ds in user_wants - existing_datasets:
            await self.middleware.call('pool.dataset.create', {'name': create_ds, 'type': 'FILESYSTEM'})
