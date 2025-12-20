import asyncio
import os

from middlewared.service import Service
from middlewared.utils.smb import SearchProtocol


class TrueSearchService(Service):
    class Config:
        private = True

    async def unavailable_reasons(self) -> list[str]:
        """
        Returns a list of reasons why the truesearch service cannot be used.
        """
        reasons = []

        # Boot pool is usually too small to fit the search index
        if await self.middleware.call('systemdataset.is_boot_pool'):
            reasons.append('The system dataset must not reside on the boot pool.')

        if await self.middleware.call('system.license') is None:
            if (await self.middleware.call('tn_connect.config'))['status'] != 'CONFIGURED':
                reasons.append(
                    'The system must be connected to TrueNAS Connect, or have an Enterprise License key installed.'
                )

        return reasons

    async def available(self) -> bool:
        """
        Whether the truesearch service can be used.
        """
        return not bool(await self.middleware.call('truesearch.unavailable_reasons'))

    async def enabled(self) -> bool:
        """
        Whether the truesearch service should be started.
        """
        return await self.available() and bool(await self.directories())

    async def directories(self) -> list[str]:
        """
        What directories will it index.
        """
        return await self.process_directories(await self.raw_directories())

    async def process_directories(self, directories: set[str]) -> list[str]:
        """
        :param directories: a list of share directories
        :return: a list of directories that TrueSearch will index

        The reason these do not match is that TrueSearch does not traverse filesystem boundaries.
        So if a share directory includes a nested dataset, it must be explicitly included in the directories list.
        Encrypted datasets are excluded from the index to prevent sensitive data being stored in index unencrypted.
        """
        pools = {directory.removeprefix('/mnt/').split('/')[0] for directory in directories}

        mountpoints = {}
        for dataset in await self.middleware.call('zfs.resource.query_impl', {
            'paths': pools,
            'properties': ['encryption', 'mountpoint'],
            'get_children': True,
        }):
            if dataset['type'] != 'FILESYSTEM':
                continue

            mountpoint = dataset['properties']['mountpoint']['value']
            if mountpoint and mountpoint != 'legacy':
                encrypted = dataset['properties']['encryption']['value'] != 'off'
                mountpoints[mountpoint] = encrypted

        result = set()
        for directory in directories:
            result |= self._processed_directories_for_directory(mountpoints, directory)

        return list(sorted(result))

    def _processed_directories_for_directory(self, mountpoints: dict[str, bool], directory: str) -> set[str]:
        result = set()
        match mountpoints.get(directory):
            case True:
                # The dataset is encrypted. Don't index this dataset.
                return set()
            case False:
                # The dataset is not encrypted. Add the directory
                result.add(directory)
                # And all the nested non-encrypted datasets
                for mountpoint, encrypted in mountpoints.items():
                    if os.path.commonpath([mountpoint, directory]) == directory and not encrypted:
                        result.add(mountpoint)

                return result
            case _:
                # Directory is not a dataset. Find its parent dataset
                parent = directory
                while parent not in ["/mnt", "/"]:
                    parent = os.path.dirname(parent)

                    match mountpoints.get(parent):
                        case True:
                            # The dataset is encrypted. Don't index this dataset.
                            return set()
                        case False:
                            return {directory}

                # Parent dataset not found
                return set()

    async def raw_directories(self) -> set[str]:
        """
        What directories should it index.
        """
        return await self.smb_directories() | await self.webshare_directories()

    async def smb_directories(self) -> set[str]:
        """
        What Samba shares directories should it index.
        """
        if not await self.middleware.call('service.started_or_enabled', 'cifs'):
            return set()

        smb_config = await self.middleware.call('smb.config')
        if SearchProtocol.SPOTLIGHT not in smb_config['search_protocols']:
            return set()

        shares = await self.middleware.call(
            'sharing.smb.query',
            [['enabled', '=', True], ['locked', '=', False], ['path', '!=', 'EXTERNAL']],
        )

        return {share['path'] for share in shares}

    async def webshare_directories(self) -> set[str]:
        """
        What WebShare shares directories should it index.
        """
        if not await self.middleware.call('service.started_or_enabled', 'webshare'):
            return set()

        webshare_config = await self.middleware.call('webshare.config')
        if not webshare_config['search']:
            return set()

        shares = await self.middleware.call(
            'sharing.webshare.query',
            [['enabled', '=', True], ['locked', '=', False]],
        )

        return {share['path'] for share in shares}

    RECONFIGURE_TIMER = None

    async def configure(self):
        """
        Start or stop the service based on whether it should be started or stopped.
        """
        if self.RECONFIGURE_TIMER is not None:
            self.RECONFIGURE_TIMER.cancel()

        enabled = await self.enabled()
        running = (await self.middleware.call('service.get_state', 'truesearch')).running

        if enabled and running:
            await (await self.middleware.call('service.control', 'RELOAD', 'truesearch')).wait(raise_error=True)
        elif enabled and not running:
            await (await self.middleware.call('service.control', 'START', 'truesearch')).wait(raise_error=True)
        elif not enabled and running:
            await (await self.middleware.call('service.control', 'STOP', 'truesearch')).wait(raise_error=True)

    async def schedule_reconfigure(self):
        """
        Reconfigure TrueSearch in 5 seconds. This is to prevent it being reconfigured too often when too many datasets
        are mounted at the time.
        """
        if self.RECONFIGURE_TIMER is not None:
            self.RECONFIGURE_TIMER.cancel()

        self.RECONFIGURE_TIMER = asyncio.get_running_loop().call_later(
            5,
            lambda: asyncio.create_task(self.configure())
        )


async def post_license_update(middleware, prev_license, *args, **kwargs):
    await middleware.call('truesearch.configure')


async def on_dataset_mounted(middleware, data):
    mount = data

    for directory in await middleware.call('truesearch.raw_directories'):
        paths = {directory, mount['mountpoint']}
        # If the mounted path is a child of the share, or the share is a child of the mounted path, reconfigure TS
        if os.path.commonpath(list(paths)) in paths:
            middleware.logger.info(
                f"Mounted path {mount['mountpoint']!r} intersects with indexed directory {directory}. "
                "Scheduling TrueSearch reload."
            )
            await middleware.call('truesearch.schedule_reconfigure')
            break


async def on_system_ready(middleware, event_type, args):
    if await middleware.call('failover.licensed'):
        return

    await middleware.call('truesearch.configure')


async def setup(middleware):
    middleware.register_hook("system.post_license_update", post_license_update)
    middleware.register_hook("zfs.dataset.mounted", on_dataset_mounted)
    middleware.event_subscribe("system.ready", on_system_ready)
