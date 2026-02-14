from __future__ import annotations

import errno
import os
import stat

from catalog_reader.train_utils import get_train_path
from middlewared.api.current import CatalogAppInfo, CatalogApps, CatalogAppVersionDetails
from middlewared.service import CallError, ServiceContext

from .apps_details import get_normalized_questions_context, retrieve_recommended_apps
from .apps_util import get_app_details as retrieve_app_details


def get_app_details(context: ServiceContext, app_name: str, options: CatalogAppVersionDetails) -> CatalogAppInfo:
    catalog = context.call_sync2(context.s.catalog.config)
    app_location = os.path.join(get_train_path(catalog.location), options.train, app_name)
    try:
        if not stat.S_ISDIR(os.stat(app_location).st_mode):
            raise CallError(f'{app_location!r} must be a directory')
    except FileNotFoundError:
        raise CallError(f'Unable to locate {app_name!r} at {app_location!r}', errno=errno.ENOENT)

    train_data = context.call_sync2(context.s.catalog.apps, CatalogApps(
        retrieve_all_trains=False,
        trains=[options.train],
    ))
    if options.train not in train_data.root:
        raise CallError(f'Unable to locate {options.train!r} train')
    elif app_name not in train_data.root[options.train].root:
        raise CallError(f'Unable to locate {app_name!r} app in {options.train!r} train')

    questions_context = context.run_coroutine(get_normalized_questions_context(context)).model_dump(by_alias=True)
    app_details = retrieve_app_details(
        app_location, train_data.root[options.train].root[app_name].model_dump(), questions_context
    )
    recommended_apps = context.run_coroutine(retrieve_recommended_apps(context))
    if options.train in recommended_apps and app_name in recommended_apps[options.train]:
        app_details['recommended'] = True

    return CatalogAppInfo.model_validate(app_details)
