from __future__ import annotations

import collections
from typing import TYPE_CHECKING, Any, Literal, overload

from middlewared.api.current import AppsIxVolumeEntry, QueryOptions, ZFSResourceQuery
from middlewared.service import ServiceContext
from middlewared.utils.filter_list import filter_list

from .ix_apps.path import get_app_mounts_ds
from .utils import to_entries

if TYPE_CHECKING:
    class _QueryGetOptions(QueryOptions):
        get: Literal[True]
        count: Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: Literal[True]
        get: Literal[False]


@overload
def query_ix_volumes(  # type: ignore[overload-overlap]
    context: ServiceContext, filters: list[Any], options: _QueryCountOptions,
) -> int: ...


@overload
def query_ix_volumes(  # type: ignore[overload-overlap]
    context: ServiceContext, filters: list[Any], options: _QueryGetOptions,
) -> AppsIxVolumeEntry: ...


@overload
def query_ix_volumes(
    context: ServiceContext, filters: list[Any], options: QueryOptions,
) -> list[AppsIxVolumeEntry]: ...


def query_ix_volumes(
    context: ServiceContext, filters: list[Any], options: QueryOptions,
) -> list[AppsIxVolumeEntry] | AppsIxVolumeEntry | int:
    if not context.call_sync2(context.s.docker.validate_state, False):
        return to_entries(filter_list([], filters, options.model_dump()), AppsIxVolumeEntry)

    docker_config = context.call_sync2(context.s.docker.config)
    if not docker_config.dataset:
        return to_entries(filter_list([], filters, options.model_dump()), AppsIxVolumeEntry)

    datasets = context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(
            paths=[get_app_mounts_ds(docker_config.dataset)],
            get_children=True,
            get_source=False,
            properties=None,
        ),
    )

    apps: dict[str, list[str]] = collections.defaultdict(list)
    for ds in datasets:
        if ds['name'].count('/') <= 3:
            continue
        name_split = ds['name'].split('/', 4)
        apps[name_split[3]].append(name_split[-1])

    volumes: list[dict[str, Any]] = []
    for app_name, app_volumes in apps.items():
        for volume in app_volumes:
            volumes.append({'name': volume, 'app_name': app_name})

    return to_entries(filter_list(volumes, filters, options.model_dump()), AppsIxVolumeEntry)
