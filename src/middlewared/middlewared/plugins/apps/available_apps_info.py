from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.api.current import (
    AppLatestItem, AppAvailableItem, CatalogApps, QueryOptions,
)
from middlewared.plugins.catalog.apps_details import CATEGORIES_SET
from middlewared.plugins.catalog.sync import sync_state
from middlewared.plugins.catalog.utils import IX_APP_NAME
from middlewared.service import ServiceContext
from middlewared.utils.filter_list import filter_list

from .utils import to_entries


def available(
    context: ServiceContext, filters: list[Any], options: QueryOptions
) -> list[AppAvailableItem] | AppAvailableItem | int:
    if not sync_state.synced:
        context.call_sync2(context.s.catalog.sync).wait_sync()

    results = []
    installed_apps = [
        (app.metadata['name'], app.metadata['train'])
        for app in context.call_sync2(context.s.app.query)
    ]

    catalog = context.call_sync2(context.s.catalog.config)
    for train, train_data in context.call_sync2(context.s.catalog.apps, CatalogApps()).root.items():
        if train not in catalog.preferred_trains:
            continue

        for app_data in train_data.root.values():
            results.append({
                'catalog': catalog.label,
                'installed': (app_data.name, train) in installed_apps,
                'train': train,
                'popularity_rank': sync_state.popularity_info.get(train, {}).get(app_data.name),
                **app_data.model_dump(),
            })

    return to_entries(filter_list(results, filters, options.model_dump()), AppAvailableItem)
