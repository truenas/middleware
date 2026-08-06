import errno

from middlewared.api.current import ZFSResourceQuery
from middlewared.service import CallError, private, Service
from middlewared.plugins.pool_.utils import CreateImplArgs, UpdateImplArgs
from middlewared.utils.filesystem.perms import enforce_dir_perms

from .utils import CONTAINER_DS_NAME, container_dataset, container_dataset_mountpoint

CONTAINER_DS_PARENT_DIR = f'/mnt/{CONTAINER_DS_NAME}'


class ContainerService(Service):
    class Config:
        cli_namespace = 'service.container'
        namespace = 'container'
        role_prefix = 'CONTAINER'

    @private
    async def ensure_pool_mountpoint(self, pool):
        """Repair the container dataset's custom mountpoint on `pool`.

        The dataset is deliberately mounted outside the pool's own tree so it cannot be shared over
        SMB, NFS, etc. by accident. That gets lost whenever the pool's mountpoints are reset: a pool
        foreign to this system, a rollback to a release without containers, or someone running
        `zfs inherit -r mountpoint`.

        Nothing reads the rootfs location back out of ZFS, so the drift does not fail loudly. The
        container simply comes up on an empty directory.

        Returns whether the mountpoint property was rewritten.
        """
        main_dataset = container_dataset(pool)
        # `container_dataset_mountpoint` returns the value without the pool's `/mnt` altroot, while
        # the value ZFS reports back has it. Both forms are needed.
        expected_prop = container_dataset_mountpoint(pool)
        expected_path = f'/mnt{expected_prop}'

        # Naming the dataset explicitly is load-bearing: it is an internal path, and `query_impl`
        # only returns those when the caller asks for them by name.
        resources = await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[main_dataset], properties=['mountpoint'])
        )
        if not resources:
            return False

        current = resources[0]['properties']['mountpoint']['value']
        if current == expected_path:
            return False

        # Something may already be mounted where this dataset is about to move. Setting the
        # mountpoint would stack ours on top and silently hide theirs, so refuse instead.
        try:
            statfs = await self.middleware.call('filesystem.statfs', expected_path)
        except CallError as e:
            if e.errno != errno.ENOENT:
                raise
            # Path does not exist yet. ZFS creates it on mount.
        else:
            if statfs['dest'] == expected_path and statfs['source'] != main_dataset:
                self.logger.error(
                    '%s: not repairing mountpoint, %r is already the mountpoint of %r',
                    main_dataset, expected_path, statfs['source'],
                )
                return False

        await self.middleware.call(
            'pool.dataset.update_impl',
            UpdateImplArgs(name=main_dataset, zprops={'mountpoint': expected_prop})
        )
        self.logger.info(
            '%s: reset mountpoint from %r to %r', main_dataset, current, expected_path
        )
        return True

    @private
    async def ensure_datasets(self, pool):
        main_dataset = container_dataset(pool)
        main_dataset_mountpoint = container_dataset_mountpoint(pool)

        datasets = [f'{main_dataset}/containers', f'{main_dataset}/images']

        existing_datasets = set()
        for dataset in await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[main_dataset] + datasets, properties=None)
        ):
            if dataset['type'] != 'FILESYSTEM':
                raise CallError(f'Expected dataset {dataset["name"]!r} to be FILESYSTEM, but it is {dataset["type"]}')

            existing_datasets.add(dataset['name'])

        # Repair drifted mountpoints so the mount below lands in the right place.
        await self.ensure_pool_mountpoint(pool)

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
