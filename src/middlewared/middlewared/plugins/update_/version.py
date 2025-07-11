import asyncio

from middlewared.api import api_method
from middlewared.api.current import UpdateAvailableVersionsArgs, UpdateAvailableVersionsResult
from middlewared.service import private, Service
from .utils import can_update


class UpdateService(Service):

    @api_method(
        UpdateAvailableVersionsArgs,
        UpdateAvailableVersionsResult,
        roles=['SYSTEM_UPDATE_READ'],
    )
    async def available_versions(self):
        """
        TrueNAS versions available for update.
        """
        trains = await self.middleware.call('update.get_trains')

        next_trains = await self.middleware.call('update.get_next_trains_names', trains)

        versions = []
        for train, releases in zip(
            next_trains,
            await asyncio.gather(*[self.middleware.call('update.get_train_releases', train) for train in next_trains]),
        ):
            for version, manifest in reversed(releases.items()):
                if await self.can_update_to(version):
                    versions.append({
                        'train': train,
                        'version': await self.version_from_manifest({**manifest, 'version': version}),
                    })

        return versions

    @private
    async def can_update_to(self, version):
        return can_update(await self.middleware.call('system.version_short'), version)

    @private
    async def version_from_manifest(self, manifest):
        return {
            'version': manifest['version'],
            'manifest': manifest,
            'release_notes_url': (
                await self.middleware.call("system.release_notes_url", manifest["version"])
            ),
        }
