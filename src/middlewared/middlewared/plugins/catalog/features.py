from __future__ import annotations

import errno
import json
import os
import typing

from apps_schema.features import FEATURES
from middlewared.service import CallError, ServiceContext

from .apps_util import min_max_scale_version_check_update_impl


def get_feature_map(context: ServiceContext, cache: bool = True) -> dict[str, dict[str, dict[str, typing.Any]]]:
    if cache and context.middleware.call_sync('cache.has_key', 'catalog_feature_map'):
        cached: dict[str, dict[str, dict[str, typing.Any]]] = context.middleware.call_sync(
            'cache.get', 'catalog_feature_map',
        )
        return cached
    catalog = context.call_sync2(context.s.catalog.config)

    path = os.path.join(catalog.location, 'features_capability.json')
    if not os.path.exists(path):
        raise CallError('Unable to retrieve feature capability mapping for SCALE versions', errno=errno.ENOENT)

    with open(path, 'r') as f:
        mapping: dict[str, dict[str, dict[str, typing.Any]]] = json.loads(f.read())

    context.middleware.call_sync('cache.put', 'catalog_feature_map', mapping, 86400)

    return mapping


async def missing_feature_error_message(context: ServiceContext, missing_features: set[str]) -> str:
    try:
        mapping = await context.to_thread(get_feature_map, context)
    except Exception as e:
        context.logger.error('Unable to retrieve feature mapping for SCALE versions: %s', e)
        mapping = {}

    error_str = 'Catalog app version is not supported due to following missing features:\n'
    for index, feature in enumerate(missing_features):
        train_message = ''
        for k, v in mapping.get(feature, {}).items():
            train_message += f'\nFor {k.capitalize()!r} train:\nMinimum SCALE version: {v["min"]}\n'
            if v.get('max'):
                train_message += f'Maximum SCALE version: {v["max"]}'
            else:
                train_message += f'Maximum SCALE version: Latest available {k.capitalize()!r} release'

        error_str += f'{index + 1}) {feature}{f"{train_message}" if train_message else ""}\n\n'

    return error_str


async def version_supported_error_check(context: ServiceContext, version_details: dict[str, typing.Any]) -> None:
    if version_details['supported']:
        return

    if not version_details['healthy']:
        raise CallError(version_details['healthy_error'])

    # There will be 2 scenarios now because of which a version might not be supported
    # 1) Missing features
    # 2) Minimum/maximum scale version check specified

    error_str = ''
    missing_features = set(version_details['required_features']) - set(FEATURES)
    if missing_features:
        error_str = await missing_feature_error_message(context, missing_features)

    if err := min_max_scale_version_check_update_impl(version_details, False):
        prefix = '\n\n' if error_str else ''
        error_str = f'{error_str}{prefix}{" Also" if error_str else ""}{err}'

    raise CallError(error_str)
