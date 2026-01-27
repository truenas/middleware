from __future__ import annotations

import asyncio

from middlewared.api.current import UpdateAvailableVersion, UpdateStatusNewVersion
from middlewared.service import ServiceContext
from .trains import ReleaseManifest
from .utils import can_update
from .trains import get_trains, get_train_releases, get_next_trains_names, release_notes


async def available_versions(context: ServiceContext) -> list[UpdateAvailableVersion]:
    trains = await get_trains(context)

    next_trains = await get_next_trains_names(context, trains)

    versions = []
    for train, releases in zip(
        next_trains,
        await asyncio.gather(*[get_train_releases(context, train) for train in next_trains]),
    ):
        for version, manifest in reversed(releases.items()):
            if await can_update_to(context, version):
                versions.append(UpdateAvailableVersion(
                    train=train,
                    version=await version_from_manifest(
                        context,
                        ReleaseManifest(**{**manifest.model_dump(), "train": train, "version": version})
                    ),
                ))

    return versions


async def can_update_to(context: ServiceContext, version: str) -> bool:
    return can_update(await context.middleware.call('system.version_short'), version)


async def version_from_manifest(context: ServiceContext, manifest: ReleaseManifest) -> UpdateStatusNewVersion:
    return UpdateStatusNewVersion(
        version=manifest.version,
        manifest=manifest.model_dump(),
        release_notes=await release_notes(context, manifest.train, manifest.filename),
        release_notes_url=await context.middleware.call("system.release_notes_url", manifest.version),
    )
