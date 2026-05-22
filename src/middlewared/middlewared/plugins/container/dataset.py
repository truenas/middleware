import os

from middlewared.api.current import ZFSResourceQuery
from middlewared.service import CallError, private, Service
from middlewared.plugins.pool_.utils import CreateImplArgs
from middlewared.utils.filesystem.perms import enforce_dir_perms

from .utils import CONTAINER_DS_NAME, container_dataset, container_dataset_mountpoint

CONTAINER_DS_PARENT_DIR = f'/mnt/{CONTAINER_DS_NAME}'


class ContainerService(Service):
    class Config:
        cli_namespace = 'service.container'
        namespace = 'container'
        role_prefix = 'CONTAINER'

    @private
    async def ensure_datasets(self, pool):
        main_dataset = container_dataset(pool)
        main_dataset_mountpoint = container_dataset_mountpoint(pool)

        datasets = [f'{main_dataset}/containers', f'{main_dataset}/images']

        existing_datasets = set()
        for dataset in await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[main_dataset] + datasets, properties=['mountpoint'])
        ):
            if dataset['type'] != 'FILESYSTEM':
                raise CallError(f'Expected dataset {dataset["name"]!r} to be FILESYSTEM, but it is {dataset["type"]}')

            if dataset['name'] == main_dataset:
                main_dataset_mountpoint_value = f'/mnt{main_dataset_mountpoint}'
                if dataset['properties']['mountpoint']['value'] != main_dataset_mountpoint_value:
                    raise CallError(
                        f'Expected dataset {dataset["name"]} to have mountpoint of {main_dataset_mountpoint_value!r}, '
                        f'but it is {dataset["properties"]["mountpoint"]["value"]!r}.'
                    )

            existing_datasets.add(dataset['name'])

        if main_dataset not in existing_datasets:
            await self.middleware.call(
                'pool.dataset.create_impl',
                CreateImplArgs(
                    name=main_dataset,
                    ztype='FILESYSTEM',
                    zprops={
                        'mountpoint': main_dataset_mountpoint,
                        'acltype': 'posix',
                        'aclmode': 'discard',
                        'snapdir': 'hidden',
                    },
                )
            )

        if not await self.middleware.run_in_thread(os.path.ismount, f'/mnt{main_dataset_mountpoint}'):
            await self.call2(self.s.zfs.resource.mount, main_dataset)

        for dataset in datasets:
            if dataset not in existing_datasets:
                await self.middleware.call(
                    'pool.dataset.create_impl',
                    CreateImplArgs(name=dataset, ztype='FILESYSTEM')
                )
            await self.call2(self.s.zfs.resource.mount, dataset)

        # ZFS auto-creates CONTAINER_DS_PARENT_DIR as a side effect of mounting the
        # per-pool dataset. Restrict it so non-root host users can't traverse to
        # any container's on-disk rootfs (UID-collision exposure for apps user etc.).
        await self.middleware.run_in_thread(enforce_dir_perms, CONTAINER_DS_PARENT_DIR)
