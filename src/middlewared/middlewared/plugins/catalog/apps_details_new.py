from __future__ import annotations

import contextlib
import json
import os
from typing import Any

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
    AppCertificateChoices, AppIpChoices, CatalogApps, CatalogEntry, SystemGeneralEntry, SystemGeneralTimezoneChoices,
)
from middlewared.service import ServiceContext

from .utils import OFFICIAL_LABEL


CATEGORIES_SET: set[str] = set()


class NormalizedQuestions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timezones: SystemGeneralTimezoneChoices
    general_config: SystemGeneralEntry = Field(alias='system.general.config')
    certificates: AppCertificateChoices
    ip_choices: AppIpChoices
    gpu_choices: list[dict[str, Any]]


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

    data = retrieve_recommended_apps_from_catalog_reader((await context.middleware.call('catalog.config'))['location'])
    await context.middleware.call('cache.put', cache_key, data)
    return data
