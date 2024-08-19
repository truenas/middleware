import contextlib
import os
import shutil
import uuid

from datetime import datetime

from middlewared.service import CallError, private, Service

from .state_utils import (
    DatasetDefaults, docker_datasets, IX_APPS_MOUNT_PATH, IX_APPS_DIR_NAME, missing_required_datasets,
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
    def move_conflicting_dir(self, ds_name):
        base_ds_name = os.path.basename(ds_name)
        from_path = os.path.join(IX_APPS_MOUNT_PATH, base_ds_name)
        if ds_name == 'ix-apps':  # FIXME: we need to specify this globally
            from_path = IX_APPS_MOUNT_PATH

        with contextlib.suppress(FileNotFoundError):
            # can't stop someone from manually creating same name
            # directories on disk so we'll just move them
            shutil.move(from_path, f'{from_path}-{str(uuid.uuid4())[:4]}-{datetime.now().isoformat()}')

    @private
    def create_update_docker_datasets_impl(self, docker_ds):
        create_props_default = DatasetDefaults.to_dict()
        update_props_default = DatasetDefaults.update_only()
        expected_docker_datasets = docker_datasets(docker_ds)
        actual_docker_datasets = {
            k['id']: v['properties'] for k, v in self.middleware.call_sync(
                'zfs.dataset.query', [['id', 'in', expected_docker_datasets]], {
                    'extra': {
                        'properties': list(update_props_default.keys()),
                        'retrieve_children': False,
                        'user_properties': False,
                    }
                }
            ).items()
        }
        for dataset_name in expected_docker_datasets:
            if existing_dataset := actual_docker_datasets.get(dataset_name):
                for prop_name, prop_info in existing_dataset['properties'].items():
                    if prop_info['value'] != update_props_default[prop_name]:
                        # if any of the zfs properties dont match what we expect
                        # we'll update all properties
                        self.middleware.call_sync(
                            'zfs.dataset.update', dataset_name, {
                                'properties': {k: {'value': v} for k, v in update_props_default.items()}
                            }
                        )
                        break

            else:
                self.move_conflicting_dir(dataset_name)
                if dataset_name == 'ix-apps':  # FIXME: we need to specify this globally
                    create_props_default = create_props_default | {'mountpoint': f'/{IX_APPS_DIR_NAME}'}
                self.middleware.call_sync('zfs.dataset.create', {
                    'name': dataset_name, 'type': 'FILESYSTEM', 'properties': create_props_default,
                })

    @private
    async def create_update_docker_datasets(self, docker_ds):
        """The following logic applies:

            1. create the docker datasets fresh (if they dont exist)
            2. OR update the docker datasets zfs properties if they
                don't match reality.

            NOTE: this method needs to be optimized as much as possible
            since this is called on docker state change for each docker
            dataset
        """
        await self.middleware.run_in_thread(self.create_update_docker_datasets_impl, docker_ds)
