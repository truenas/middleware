from __future__ import annotations

import aiohttp
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from middlewared.api.current import CatalogApps
from middlewared.service import CallError, ServiceContext
from middlewared.utils.network import check_internet_connectivity

from .apps_details import retrieve_recommended_apps
from .features import get_feature_map
from .git_utils import pull_clone_repository
from .utils import OFFICIAL_LABEL, OFFICIAL_CATALOG_REPO, OFFICIAL_CATALOG_BRANCH

if TYPE_CHECKING:
    from middlewared.job import Job


STATS_URL: str = 'https://telemetry.sys.truenas.net/apps/truenas-apps-stats.json'


@dataclass
class SyncState:
    synced: bool = False
    popularity_info: dict[str, Any] = field(default_factory=dict)


sync_state = SyncState()


def get_synced_state() -> bool:
    """Return whether the catalog has been synced at least once."""
    return sync_state.synced


async def update_popularity_cache(context: ServiceContext) -> None:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        try:
            async with session.get(STATS_URL) as response:
                response.raise_for_status()
                sync_state.popularity_info = {
                    k.lower(): v for k, v in (await response.json()).items()
                    # Making sure we have a consistent format as for trains we see capitalized
                    # entries in the file
                }
        except Exception as e:
            context.logger.error('Failed to fetch popularity stats for apps: %r', e)


async def update_git_repository(context: ServiceContext, location: str, repository: str, branch: str) -> None:
    await context.middleware.call('network.general.will_perform_activity', 'catalog')
    try:
        await context.to_thread(pull_clone_repository, repository, location, branch)
    except Exception:
        # We will check if there was a network issue and raise an error in a nicer format if that's the case
        if error := await check_internet_connectivity():
            raise CallError(error)

        raise


async def sync(context: ServiceContext, job: Job) -> None:
    try:
        catalog = await context.call2(context.s.catalog.config)

        job.set_progress(5, 'Updating catalog repository')
        await update_git_repository(context, catalog.location, OFFICIAL_CATALOG_REPO, OFFICIAL_CATALOG_BRANCH)
        job.set_progress(15, 'Reading catalog information')
        # Update feature map cache whenever official catalog is updated
        await context.to_thread(get_feature_map, context, False)
        await retrieve_recommended_apps(context, False)

        await context.call2(context.s.catalog.apps, CatalogApps(
            cache=False,
            cache_only=False,
            retrieve_all_trains=True,
        ))
        await update_popularity_cache(context)
    except Exception as e:
        await context.middleware.call(
            'alert.oneshot_create', 'CatalogSyncFailed', {'catalog': OFFICIAL_LABEL, 'error': str(e)}
        )
        raise
    else:
        await context.middleware.call('alert.oneshot_delete', 'CatalogSyncFailed', OFFICIAL_LABEL)
        job.set_progress(100, f'Synced {OFFICIAL_LABEL!r} catalog')
        sync_state.synced = True
        context.create_task(context.middleware.call('app.check_upgrade_alerts'))
