from __future__ import annotations

import contextlib
import json
import os
import typing

from apps_ci.names import CACHED_CATALOG_FILE_NAME
from apps_validation.json_schema_utils import CATALOG_JSON_SCHEMA
from catalog_reader.app_utils import get_app_details_base
from catalog_reader.catalog import retrieve_train_names
from catalog_reader.train_utils import get_train_path
from catalog_reader.recommended_apps import retrieve_recommended_apps as retrieve_recommended_apps_from_catalog_reader
from datetime import datetime
from jsonschema import validate as json_schema_validate, ValidationError as JsonValidationError
from pydantic import BaseModel, ConfigDict, Field

from middlewared.api.current import (
    AppCertificateChoices, AppIpChoices, CatalogApps, CatalogAppsResponse, CatalogEntry,
    SystemGeneralEntry, SystemGeneralTimezoneChoices,
)
from middlewared.service import ServiceContext

from .apps_util import get_app_version_details
from .utils import get_cache_key, OFFICIAL_LABEL


CATEGORIES_SET: set[str] = set()


class NormalizedQuestions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timezones: SystemGeneralTimezoneChoices
    general_config: SystemGeneralEntry = Field(alias='system.general.config')
    certificates: AppCertificateChoices
    ip_choices: AppIpChoices
    gpu_choices: list[dict[str, typing.Any]]


def train_to_apps_version_mapping(context: ServiceContext) -> dict[str, dict[str, dict[str, str]]]:
    mapping = {}
    for train, train_data in apps(context, CatalogApps(
        cache=True,
        cache_only=True,
    )).root.items():
        mapping[train] = {}
        for app_data in train_data.root.values():
            mapping[train][app_data.name] = {
                'version': app_data.latest_version,
                'app_version': app_data.latest_app_version,
            }

    return mapping


def apps(context: ServiceContext, options: CatalogApps) -> CatalogAppsResponse:
    catalog = context.call_sync2(context.s.catalog.config)
    all_trains = options.retrieve_all_trains
    cache_available = False

    if options.cache:
        cache_key = get_cache_key(catalog.label)
        try:
            orig_cached_data = context.middleware.call_sync('cache.get', cache_key)
        except KeyError:
            orig_cached_data = None

        cache_available = orig_cached_data is not None

    if options.cache and options.cache_only and not cache_available:
        return CatalogAppsResponse.model_validate({})

    if options.cache and cache_available:
        cached_data = {}
        for train in orig_cached_data:
            if not all_trains and train not in options.trains:
                continue

            train_data = {}
            for catalog_app in orig_cached_data[train]:
                train_data[catalog_app] = {k: v for k, v in orig_cached_data[train][catalog_app].items()}

            cached_data[train] = train_data

        return CatalogAppsResponse.model_validate(cached_data)
    elif not os.path.exists(catalog.location):
        return CatalogAppsResponse.model_validate({})

    if all_trains:
        # We can only safely say that the catalog is healthy if we retrieve data for all trains
        context.middleware.call_sync('alert.oneshot_delete', 'CatalogNotHealthy', catalog.label)

    trains = get_trains(context, catalog, options)

    if all_trains:
        # We will only update cache if we are retrieving data of all trains for a catalog
        # which happens when we sync catalog(s) periodically or manually
        # We cache for 90000 seconds giving system an extra 1 hour to refresh it's cache which
        # happens after 24h - which means that for a small amount of time it's possible that user
        # come with a case where system is trying to access cached data but it has expired and it's
        # reading again from disk hence the extra 1 hour.
        context.middleware.call_sync('cache.put', get_cache_key(catalog.label), trains, 90000)

    return CatalogAppsResponse.model_validate(trains)


def get_trains(context: ServiceContext, catalog: CatalogEntry, options: CatalogApps) -> dict[str, dict]:
    if os.path.exists(os.path.join(catalog.location, CACHED_CATALOG_FILE_NAME)):
        # If the data is malformed or something similar, let's read the data then from filesystem
        try:
            return retrieve_trains_data_from_json(context, catalog, options)
        except (json.JSONDecodeError, JsonValidationError):
            context.logger.error('Invalid catalog json file specified for %r catalog', catalog.id)

    return {}


def retrieve_trains_data_from_json(
    context: ServiceContext, catalog: CatalogEntry, options: CatalogApps
) -> dict[str, dict]:
    global CATEGORIES_SET

    trains_to_traverse = retrieve_train_names(
        get_train_path(catalog.location), options.retrieve_all_trains, options.trains
    )
    with open(os.path.join(catalog.location, CACHED_CATALOG_FILE_NAME), 'r') as f:
        catalog_data = json.loads(f.read())
        json_schema_validate(catalog_data, CATALOG_JSON_SCHEMA)

        data = {k: v for k, v in catalog_data.items() if k in trains_to_traverse}

    if catalog.label == OFFICIAL_LABEL:
        recommended_apps = context.run_coroutine(retrieve_recommended_apps(context, False))
    else:
        recommended_apps = {}

    unhealthy_apps = set()
    for train in data:
        for app in data[train]:
            # We normalize keys here, why this needs to be done is that specifying some keys which probably
            # will be monotonous for an app dev to specify in each version of the app if he is not consuming them
            # in his app. This way we can ensure that we have all the keys present for each app in each train
            # from our consumers perspective.
            data[train][app].update({
                **{k: v for k, v in get_app_details_base(False).items() if k not in data[train][app]},
                'location': os.path.join(get_train_path(catalog.location), train, app),
            })
            if data[train][app]['last_update']:
                data[train][app]['last_update'] = datetime.strptime(
                    data[train][app]['last_update'], '%Y-%m-%d %H:%M:%S'
                )

            if data[train][app]['healthy'] is False:
                unhealthy_apps.add(f'{app} ({train} train)')
            if train in recommended_apps and app in recommended_apps[train]:
                data[train][app]['recommended'] = True

            CATEGORIES_SET.update(data[train][app].get('categories') or [])

    if unhealthy_apps:
        context.middleware.call_sync(
            'alert.oneshot_create', 'CatalogNotHealthy', {
                'catalog': catalog.id, 'apps': ', '.join(unhealthy_apps)
            }
        )

    return data


async def get_normalized_questions_context(context: ServiceContext) -> NormalizedQuestions:
    return NormalizedQuestions.model_validate({
        'timezones': await context.middleware.call('system.general.timezone_choices'),
        'system.general.config': await context.middleware.call('system.general.config'),
        'certificates': await context.middleware.call('app.certificate_choices'),
        'ip_choices': await context.middleware.call('app.ip_choices'),
        'gpu_choices': await context.middleware.call('app.gpu_choices_internal'),
    })


async def retrieve_recommended_apps(context: ServiceContext, cache: bool = True) -> dict[str, list[str]]:
    cache_key = 'recommended_apps'
    if cache:
        with contextlib.suppress(KeyError):
            return await context.middleware.call('cache.get', cache_key)

    data = retrieve_recommended_apps_from_catalog_reader((await context.call2(context.s.catalog.config)).location)
    await context.middleware.call('cache.put', cache_key, data)
    return data


def app_version_details(
    context: ServiceContext, version_path: str, questions_context: NormalizedQuestions | None = None
) -> dict[str, typing.Any]:
    if questions_context is None:
        questions_context = context.run_coroutine(get_normalized_questions_context(context))

    return get_app_version_details(version_path, questions_context.model_dump(by_alias=True))
