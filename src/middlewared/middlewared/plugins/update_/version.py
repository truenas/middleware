import asyncio
from typing import Any

from middlewared.api import api_method
from middlewared.api.current import (
    UpdateAvailableVersion, UpdateAvailableVersionsArgs, UpdateAvailableVersionsResult, UpdateStatusNewVersion,
)
from middlewared.service import private, Service
from .trains import ReleaseManifest
from .utils import can_update


class UpdateService(Service):

    @api_method(
        UpdateAvailableVersionsArgs,
        UpdateAvailableVersionsResult,
        roles=['SYSTEM_UPDATE_READ'],
        check_annotations=True,
    )
    async def available_versions(self) -> list[UpdateAvailableVersion]:
        """
        TrueNAS versions available for update.
        """
        trains = await self.call2(self.s.update.get_trains)

        next_trains = await self.call2(self.s.update.get_next_trains_names, trains)

        versions = []
        for train, releases in zip(
            next_trains,
            await asyncio.gather(*[self.call2(self.s.update.get_train_releases, train) for train in next_trains]),
        ):
            for version, manifest in reversed(releases.items()):
                if await self.can_update_to(version):
                    versions.append(UpdateAvailableVersion(
                        train=train,
                        version=await self.version_from_manifest(
                            ReleaseManifest(**{**manifest.model_dump(), "train": train, "version": version})
                        ),
                    ))

        return versions

    @private
    async def can_update_to(self, version: str) -> bool:
        return can_update(await self.middleware.call('system.version_short'), version)

    @private
    async def version_from_manifest(self, manifest: ReleaseManifest) -> UpdateStatusNewVersion:
        return UpdateStatusNewVersion(
            version=manifest.version,
            manifest=manifest.model_dump(),
            release_notes=await self.call2(self.s.update.release_notes, manifest.train, manifest.filename),
            release_notes_url=await self.middleware.call("system.release_notes_url", manifest.version),
        )
