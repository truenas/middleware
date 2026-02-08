import contextlib
import json
import os

from apps_ci.names import CACHED_CATALOG_FILE_NAME
from jsonschema import validate as json_schema_validate, ValidationError as JsonValidationError

from middlewared.api import api_method
from middlewared.api.current import CatalogAppsArgs, CatalogAppsResult
from middlewared.service import private, Service

from .apps_details_new import get_normalized_questions_context, retrieve_recommended_apps
from .apps_util import get_app_version_details
from .utils import get_cache_key, OFFICIAL_LABEL


class CatalogService(Service):

    class Config:
        cli_namespace = 'app.catalog'

    CATEGORIES_SET = set()

    @private
    def train_to_apps_version_mapping(self):
        mapping = {}
        for train, train_data in self.apps({
            'cache': True,
            'cache_only': True,
        }).items():
            mapping[train] = {}
            for app_data in train_data.values():
                mapping[train][app_data['name']] = {
                    'version': app_data['latest_version'],
                    'app_version': app_data['latest_app_version'],
                }

        return mapping

    @private
    def cached(self, label):
        return self.middleware.call_sync('cache.has_key', get_cache_key(label))

    @api_method(CatalogAppsArgs, CatalogAppsResult, roles=['CATALOG_READ'])
    def apps(self, options):
        """
        Retrieve apps details for `label` catalog.

        `options.cache` is a boolean which when set will try to get apps details for `label` catalog from cache
        if available.

        `options.cache_only` is a boolean which when set will force usage of cache only for retrieving catalog
        information. If the content for the catalog in question is not cached, no content would be returned. If
        `options.cache` is unset, this attribute has no effect.

        `options.retrieve_all_trains` is a boolean value which when set will retrieve information for all the trains
        present in the catalog ( it is set by default ).

        `options.trains` is a list of train name(s) which will allow selective filtering to retrieve only information
        of desired trains in a catalog. If `options.retrieve_all_trains` is set, it has precedence over `options.train`.
        """
        catalog = self.middleware.call_sync('catalog.config')
        all_trains = options['retrieve_all_trains']
        cache_available = False

        if options['cache']:
            cache_key = get_cache_key(catalog['label'])
            try:
                orig_cached_data = self.middleware.call_sync('cache.get', cache_key)
            except KeyError:
                orig_cached_data = None

            cache_available = orig_cached_data is not None

        if options['cache'] and options['cache_only'] and not cache_available:
            return {}

        if options['cache'] and cache_available:
            cached_data = {}
            for train in orig_cached_data:
                if not all_trains and train not in options['trains']:
                    continue

                train_data = {}
                for catalog_app in orig_cached_data[train]:
                    train_data[catalog_app] = {k: v for k, v in orig_cached_data[train][catalog_app].items()}

                cached_data[train] = train_data

            return cached_data
        elif not os.path.exists(catalog['location']):
            return {}

        if all_trains:
            # We can only safely say that the catalog is healthy if we retrieve data for all trains
            self.middleware.call_sync('alert.oneshot_delete', 'CatalogNotHealthy', catalog['label'])

        trains = self.get_trains(catalog, options)

        if all_trains:
            # We will only update cache if we are retrieving data of all trains for a catalog
            # which happens when we sync catalog(s) periodically or manually
            # We cache for 90000 seconds giving system an extra 1 hour to refresh it's cache which
            # happens after 24h - which means that for a small amount of time it's possible that user
            # come with a case where system is trying to access cached data but it has expired and it's
            # reading again from disk hence the extra 1 hour.
            self.middleware.call_sync('cache.put', get_cache_key(catalog['label']), trains, 90000)

        return trains

    @private
    def app_version_details(self, version_path, questions_context=None):
        if not questions_context:
            questions_context = self.context.run_coroutine(
                get_normalized_questions_context(self.context)
            ).model_dump(by_alias=True)
        return get_app_version_details(version_path, questions_context)

    @private
    def retrieve_mapped_categories(self):
        return self.CATEGORIES_SET
