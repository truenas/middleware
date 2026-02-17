from typing import Any

from middlewared.api import api_method
from middlewared.api.current import (
    AppCategoriesArgs, AppCategoriesResult, AppAvailableItem, AppLatestItem,
    AppSimilarArgs, AppSimilarResult,
)
from middlewared.service import filterable_api_method, Service
from middlewared.utils.filter_list import filter_list

from .apps_details import CATEGORIES_SET
from .sync import sync_state
from .utils import IX_APP_NAME


class AppService(Service):

    class Config:
        cli_namespace = 'app'

    @filterable_api_method(item=AppLatestItem, roles=['CATALOG_READ'])
    async def latest(self, filters: list[Any], options: dict[str, Any]) -> Any:
        """
        Retrieve latest updated apps.
        """
        return filter_list(
            await self.middleware.call(
                'app.available', [
                    ['last_update', '!=', None], ['name', '!=', IX_APP_NAME],
                ], {'order_by': ['-last_update']}
            ), filters, options
        )

    @filterable_api_method(item=AppAvailableItem, roles=['CATALOG_READ'])
    def available(self, filters: list[Any], options: dict[str, Any]) -> Any:
        """
        Retrieve all available applications from all configured catalogs.
        """
        if not sync_state.synced:
            self.middleware.call_sync('catalog.sync').wait_sync()

        results: list[dict[str, Any]] = []
        installed_apps = [
            (app['metadata']['name'], app['metadata']['train'])
            for app in self.middleware.call_sync('app.query')
        ]

        catalog = self.middleware.call_sync('catalog.config')
        for train, train_data in self.middleware.call_sync('catalog.apps', {}).root.items():
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

        return filter_list(results, filters, options)

    @api_method(AppCategoriesArgs, AppCategoriesResult, roles=['CATALOG_READ'])
    async def categories(self) -> list[str]:
        """
        Retrieve list of valid categories which have associated applications.
        """
        return sorted(list(CATEGORIES_SET))

    @api_method(AppSimilarArgs, AppSimilarResult, roles=['CATALOG_READ'])
    def similar(self, app_name: str, train: str) -> list[dict[str, Any]]:
        """
        Retrieve applications which are similar to `app_name`.
        """
        available_apps = self.available([], {})
        app = filter_list(
            available_apps, [['name', '=', app_name], ['train', '=', train]], {'get': True}
        )
        similar_apps: dict[str, dict[str, Any]] = {}

        # Calculate the number of common categories/tags between app and other apps
        app_categories = set(app['categories'])
        app_tags = set(app['tags'])
        app_similarity: dict[str, int] = {}

        for to_check_app in available_apps:
            if all(to_check_app[k] == app[k] for k in ('name', 'catalog', 'train')):
                continue

            common_categories = set(to_check_app['categories']).intersection(app_categories)
            common_tags = set(to_check_app['tags']).intersection(app_tags)
            similarity_score = len(common_categories) + len(common_tags)
            if similarity_score:
                app_similarity[to_check_app['name']] = similarity_score
                similar_apps[to_check_app['name']] = to_check_app

        # Sort apps based on the similarity score in descending order
        sorted_apps = sorted(app_similarity.keys(), key=lambda x: app_similarity[x], reverse=True)

        return [similar_apps[a] for a in sorted_apps]
