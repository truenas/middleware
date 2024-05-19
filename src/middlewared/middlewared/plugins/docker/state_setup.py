import os
import shutil
import uuid

from datetime import datetime

from middlewared.service import private, Service

from .state_utils import DATASET_DEFAULTS, docker_datasets, docker_dataset_custom_props, docker_dataset_update_props
from .utils import applications_ds_name


class DockerSetupService(Service):

    class Config:
        namespace = 'docker.setup'
        private = True

    @private
    async def status_change(self):
        config = await self.middleware.call('docker.config')
        if not config['pool']:
            return

        await self.pools(config)

    @private
    async def pools(self, config):
        return await self.create_update_docker_datasets(applications_ds_name(config['pool']))

    @private
    async def create_update_docker_datasets(self, docker_ds):
        create_props_default = DATASET_DEFAULTS.copy()
        for dataset_name in docker_datasets(docker_ds):
            custom_props = docker_dataset_custom_props(dataset_name.split('/', 1)[-1])
            # got custom properties, need to re-calculate
            # the update and create props.
            create_props = dict(create_props_default, **custom_props) if custom_props else create_props_default
            update_props = docker_dataset_update_props(create_props)

            dataset = await self.middleware.call(
                'zfs.dataset.query', [['id', '=', dataset_name]], {
                    'extra': {
                        'properties': list(update_props),
                        'retrieve_children': False,
                        'user_properties': False,
                    }
                }
            )
            if not dataset:
                test_path = os.path.join('/mnt', dataset_name)
                if self.middleware.run_in_thread(os.path.exists, test_path):
                    await self.middleware.run_in_thread(
                        shutil.move, test_path, f'{test_path}-{str(uuid.uuid4())[:4]}-{datetime.now().isoformat()}',
                    )
                await self.middleware.call(
                    'zfs.dataset.create', {
                        'name': dataset_name, 'type': 'FILESYSTEM', 'properties': create_props,
                    }
                )
                if create_props.get('mountpoint') != 'legacy':
                    # since, legacy mountpoints should not be zfs mounted.
                    await self.middleware.call('zfs.dataset.mount', dataset_name)
            elif any(val['value'] != update_props[name] for name, val in dataset[0]['properties'].items()):
                await self.middleware.call(
                    'zfs.dataset.update', dataset_name, {
                        'properties': {k: {'value': v} for k, v in update_props.items()}
                    }
                )
