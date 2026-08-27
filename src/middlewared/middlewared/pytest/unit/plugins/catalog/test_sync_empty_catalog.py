import errno
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middlewared.alert.source.catalogs import CatalogSyncFailedAlert
from middlewared.plugins.catalog.sync import sync, sync_state
from middlewared.plugins.catalog.utils import OFFICIAL_LABEL
from middlewared.service import CallError


@pytest.fixture(autouse=True)
def clean_sync_state():
    original = sync_state.synced
    sync_state.synced = False
    yield
    sync_state.synced = original


def make_context(trains):
    context = MagicMock()
    catalog = MagicMock()
    catalog.label = OFFICIAL_LABEL
    catalog.location = "/mnt/tank/ix-apps/catalogs/TRUENAS"

    catalog_apps = MagicMock()
    catalog_apps.root = trains

    async def call2(f, *args, **kwargs):
        if f is context.s.catalog.config:
            return catalog
        if f is context.s.catalog.apps:
            return catalog_apps
        return None

    context.call2 = AsyncMock(side_effect=call2)
    context.middleware.call2 = AsyncMock()
    context.to_thread = AsyncMock()
    context.create_task = MagicMock()
    return context


def alert_calls(context):
    return [call.args for call in context.middleware.call2.call_args_list]


@patch("middlewared.plugins.catalog.sync.update_popularity_cache", new_callable=AsyncMock)
@patch("middlewared.plugins.catalog.sync.retrieve_recommended_apps", new_callable=AsyncMock)
@patch("middlewared.plugins.catalog.sync.update_git_repository", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_empty_catalog_data_fails_the_sync_and_alerts(git, recommended, popularity):
    context = make_context({})

    with pytest.raises(CallError) as exc_info:
        await sync(context, MagicMock())

    assert exc_info.value.errno == errno.ENODATA
    assert sync_state.synced is False

    created = [args for args in alert_calls(context) if isinstance(args[-1], CatalogSyncFailedAlert)]
    assert len(created) == 1
    assert created[0][-1].catalog == OFFICIAL_LABEL

    popularity.assert_not_awaited()


@patch("middlewared.plugins.catalog.sync.update_popularity_cache", new_callable=AsyncMock)
@patch("middlewared.plugins.catalog.sync.retrieve_recommended_apps", new_callable=AsyncMock)
@patch("middlewared.plugins.catalog.sync.update_git_repository", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_populated_catalog_data_clears_the_alert_and_marks_synced(git, recommended, popularity):
    context = make_context({"community": {"actual-budget": {}}})

    await sync(context, MagicMock())

    assert sync_state.synced is True
    assert ("CatalogSyncFailed", OFFICIAL_LABEL) in [args[1:] for args in alert_calls(context)]
    context.create_task.assert_called_once()
