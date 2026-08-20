from unittest.mock import AsyncMock, MagicMock

import pytest

from middlewared.plugins.apps.upgrade import update_app_upgrade_alert


def make_context(train_data_available, apps=()):
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
            raise KeyError(args[0])
        return None

    context.middleware.call = AsyncMock(side_effect=call)
    return context


def call2_args(context, target):
    return [call.args[1:] for call in context.call2.call_args_list if call.args[0] is target]


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
