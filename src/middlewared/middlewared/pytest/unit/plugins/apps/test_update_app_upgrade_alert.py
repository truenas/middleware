from unittest.mock import AsyncMock, MagicMock

import pytest

from middlewared.plugins.apps.upgrade import APP_UPGRADE_ALERT_CACHE_KEY, update_app_upgrade_alert

MISSING = object()


def make_context(train_data_available, apps=(), cached=MISSING):
    context = MagicMock()

    async def call2(f, *args, **kwargs):
        if f is context.s.catalog.train_data_available:
            return train_data_available
        if f is context.s.app.query:
            return list(apps)
        return None

    context.call2 = AsyncMock(side_effect=call2)

    async def call(method, *args):
        if method == "cache.get":
            if cached is MISSING:
                raise KeyError(args[0])
            return cached
        return None

    context.middleware.call = AsyncMock(side_effect=call)
    return context


def call2_args(context, target):
    return [call.args[1:] for call in context.call2.call_args_list if call.args[0] is target]


def middleware_methods(context):
    return [call.args[0] for call in context.middleware.call.call_args_list]


@pytest.mark.asyncio
async def test_unavailable_train_data_abstains_from_deciding():
    context = make_context(train_data_available=False)

    await update_app_upgrade_alert(context)

    assert [call.args[0] for call in context.call2.call_args_list] == [context.s.catalog.train_data_available]
    context.middleware.call.assert_not_awaited()


@pytest.mark.asyncio
async def test_available_train_data_with_no_apps_clears_the_alert():
    context = make_context(train_data_available=True)

    await update_app_upgrade_alert(context)

    assert call2_args(context, context.s.alert.oneshot_delete) == [("AppUpdate", None)]
    assert call2_args(context, context.s.alert.oneshot_create) == []
    assert ("cache.put", APP_UPGRADE_ALERT_CACHE_KEY, set(), 86400) in [
        call.args for call in context.middleware.call.call_args_list
    ]


@pytest.mark.asyncio
async def test_unchanged_empty_app_set_clears_the_alert_without_rewriting_the_cache():
    context = make_context(train_data_available=True, cached=[])

    await update_app_upgrade_alert(context)

    assert call2_args(context, context.s.alert.oneshot_delete) == [("AppUpdate", None)]
    assert "cache.put" not in middleware_methods(context)
