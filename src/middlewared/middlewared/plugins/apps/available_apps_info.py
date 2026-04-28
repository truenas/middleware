from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from middlewared.api.current import (
    AppAvailableItem,
    AppLatestItem,
    CatalogApps,
    QueryOptions,
)
from middlewared.plugins.catalog.apps_details import CATEGORIES_SET
from middlewared.plugins.catalog.sync import sync_state
from middlewared.plugins.catalog.utils import IX_APP_NAME
from middlewared.service import InstanceNotFound, ServiceContext
from middlewared.utils.filter_list import filter_list

from .utils import to_entries

if TYPE_CHECKING:
    class _QueryGetOptions(QueryOptions):
        get: Literal[True]
        count: Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: Literal[True]
        get: Literal[False]


async def categories() -> list[str]:
    return sorted(list(CATEGORIES_SET))


async def latest(
    context: ServiceContext, filters: list[Any], options: QueryOptions
) -> list[AppLatestItem] | AppLatestItem | int:
    filters.extend([
        ['last_update', '!=', None],
        ['name', '!=', IX_APP_NAME],
    ])
    options.order_by.extend(['-last_update'])

    def _run() -> list[AppLatestItem] | AppLatestItem | int:
        return to_entries(
            filter_list(_available_raw(context), filters, options.model_dump()), AppLatestItem,
        )

    return await context.to_thread(_run)


@overload
def available(  # type: ignore[overload-overlap]
    context: ServiceContext, filters: list[Any], options: _QueryCountOptions,
) -> int: ...


@overload
def available(  # type: ignore[overload-overlap]
    context: ServiceContext, filters: list[Any], options: _QueryGetOptions,
) -> AppAvailableItem: ...


@overload
def available(
    context: ServiceContext, filters: list[Any], options: QueryOptions,
) -> list[AppAvailableItem]: ...


def available(
    context: ServiceContext, filters: list[Any], options: QueryOptions
) -> list[AppAvailableItem] | AppAvailableItem | int:
    return to_entries(
        filter_list(_available_raw(context), filters, options.model_dump()), AppAvailableItem,
    )


def _available_raw(context: ServiceContext) -> list[dict[str, Any]]:
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

    return results


def similar(context: ServiceContext, app_name: str, train: str) -> list[AppAvailableItem]:
    available_apps = available(context, [], QueryOptions())
    app = None
    for to_check_app in available_apps:
        if to_check_app.name == app_name and to_check_app.train == train:
            app = to_check_app
            break

    if app is None:
        raise InstanceNotFound(f'App {app_name!r} not found')

    similar_apps: dict[str, AppAvailableItem] = {}

    # Calculate the number of common categories/tags between app and other apps
    app_categories = set(app.categories)
    app_tags = set(app.tags)
    app_similarity: dict[str, int] = {}

    for to_check_app in available_apps:
        if all(getattr(to_check_app, k) == getattr(app, k) for k in ('name', 'catalog', 'train')):
            continue

        common_categories = set(to_check_app.categories).intersection(app_categories)
        common_tags = set(to_check_app.tags).intersection(app_tags)
        similarity_score = len(common_categories) + len(common_tags)
        if similarity_score:
            app_similarity[to_check_app.name] = similarity_score
            similar_apps[to_check_app.name] = to_check_app

    # Sort apps based on the similarity score in descending order
    sorted_apps = sorted(app_similarity.keys(), key=lambda x: app_similarity[x], reverse=True)

    return [similar_apps[a] for a in sorted_apps]
