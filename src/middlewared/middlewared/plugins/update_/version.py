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

        current_train_name = await self.middleware.call('update.get_current_train_name', trains)
        found_current_train = False
        valid_trains = []
        for name, data in trains['trains'].items():
            if name == current_train_name:
                found_current_train = True

            if not found_current_train:
                continue

            valid_trains.append(name)

        versions = []
        for train, manifest in zip(
            valid_trains,
            await asyncio.gather(*[self.middleware.call('update.get_train_manifest', train) for train in valid_trains]),
        ):
            versions.append({
                'train': train,
                'version': await self.version_from_manifest(manifest),
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
