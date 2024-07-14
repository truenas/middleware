import os

from middlewared.service import Service

from .utils import DATASET_DEFAULTS


class AppSchemaActions(Service):

    class Config:
        namespace = 'app.schema.action'
        private = True

    async def update_volumes(self, app_name, volumes):
        app_volume_ds = os.path.join((await self.middleware.call('docker.config'))['dataset'], 'app_mounts', app_name)

        user_wants = {app_volume_ds: {'properties': {}}} | {os.path.join(app_volume_ds, v['name']): v for v in volumes}
        existing_datasets = {
            d['id'] for d in await self.middleware.call(
                'zfs.dataset.query', [['id', 'in', list(user_wants)]], {'extra': {'retrieve_properties': False}}
            )
        }

        for create_ds in sorted(set(user_wants) - existing_datasets):
            await self.middleware.call(
                'zfs.dataset.create', {
                    'properties': user_wants[create_ds]['properties'] | DATASET_DEFAULTS,
                    'name': create_ds, 'type': 'FILESYSTEM',
                }
            )
            await self.middleware.call('zfs.dataset.mount', create_ds)
