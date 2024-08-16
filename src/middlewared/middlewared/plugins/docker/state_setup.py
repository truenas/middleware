import contextlib
import os
import shutil
import uuid

from datetime import datetime

from middlewared.service import CallError, private, Service

from .state_utils import (
    DATASET_DEFAULTS, docker_datasets, docker_dataset_custom_props, docker_dataset_update_props, IX_APPS_MOUNT_PATH,
    missing_required_datasets,
)


class DockerSetupService(Service):

    class Config:
        namespace = 'docker.setup'
        private = True

    @private
    async def validate_fs(self):
        config = await self.middleware.call('docker.config')
        if not config['pool']:
            raise CallError(f'{config["pool"]!r} pool not found.')

        if missing_datasets := missing_required_datasets({
            d['id'] for d in await self.middleware.call(
                'zfs.dataset.query', [['id', 'in', docker_datasets(config['dataset'])]], {
                    'extra': {'retrieve_properties': False, 'retrieve_children': False}
                }
            )
        }, config['dataset']):
            raise CallError(f'Missing "{", ".join(missing_datasets)}" dataset(s) required for starting docker.')

        await self.create_update_docker_datasets(config['dataset'])

        locked_datasets = [
            d['id'] for d in filter(
                lambda d: d['mountpoint'], await self.middleware.call('zfs.dataset.locked_datasets')
            )
            if d['mountpoint'].startswith(f'{config["dataset"]}/') or d['mountpoint'] in (
                f'/mnt/{k}' for k in (config['dataset'], config['pool'])
            )
        ]
        if locked_datasets:
            raise CallError(
                f'Please unlock following dataset(s) before starting docker: {", ".join(locked_datasets)}',
                errno=CallError.EDATASETISLOCKED,
            )

    @private
    async def status_change(self):
        config = await self.middleware.call('docker.config')
        if not config['pool']:
            await (await self.middleware.call('catalog.sync')).wait()
            return

        await self.create_update_docker_datasets(config['dataset'])
        await self.middleware.call('docker.state.start_service')

    @private
    async def create_update_docker_datasets(self, docker_ds):
        create_props_default = DATASET_DEFAULTS.to_dict()
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
                base_ds_name = os.path.basename(dataset_name)
                test_path = IX_APPS_MOUNT_PATH if base_ds_name == 'ix-apps' else os.path.join(
                    IX_APPS_MOUNT_PATH, base_ds_name
                )
                with contextlib.suppress(FileNotFoundError):
                    await self.middleware.run_in_thread(
                        shutil.move, test_path, f'{test_path}-{str(uuid.uuid4())[:4]}-{datetime.now().isoformat()}',
                    )
                await self.middleware.call(
                    'zfs.dataset.create', {
                        'name': dataset_name, 'type': 'FILESYSTEM', 'properties': create_props,
                    }
                )
            elif any(val['value'] != update_props[name] for name, val in dataset[0]['properties'].items()):
                await self.middleware.call(
                    'zfs.dataset.update', dataset_name, {
                        'properties': {k: {'value': v} for k, v in update_props.items()}
                    }
                )
