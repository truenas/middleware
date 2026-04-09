from __future__ import annotations

from typing import Any, Literal, overload, TYPE_CHECKING

from catalog_reader.custom_app import get_version_details

from middlewared.api.current import AppEntry, QueryOptions
from middlewared.service import InstanceNotFound, ServiceContext
from middlewared.utils.filter_list import filter_list

from .ix_apps.lifecycle import get_current_app_config
from .ix_apps.query import list_apps
from .ix_apps.path import get_app_parent_volume_ds, get_installed_app_path, get_installed_app_version_path


if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job

    class _QueryGetOptions(QueryOptions):
        get: Literal[True]
        count: Literal[False]

    class _QueryCountOptions(QueryOptions):
        count: Literal[True]
        get: Literal[False]


def _to_entries(result: list[dict[str, Any]] | dict[str, Any] | int) -> list[AppEntry] | AppEntry | int:
    if isinstance(result, int):
        return result
    if isinstance(result, dict):
        return AppEntry(**result)
    return [AppEntry(**row) for row in result]


@overload
def query_apps(context: ServiceContext, filters: list[Any], options: _QueryCountOptions, app: App | None = None) -> int: ...  # type: ignore[overload-overlap]

@overload
def query_apps(context: ServiceContext, filters: list[Any], options: _QueryGetOptions, app: App | None = None) -> AppEntry: ...  # type: ignore[overload-overlap]

@overload
def query_apps(
    context: ServiceContext, filters: list[Any], options: QueryOptions, app: App | None = None,
) -> list[AppEntry]: ...

def query_apps(
    context: ServiceContext, filters: list[Any], options: QueryOptions, app: App | None = None,
) -> list[AppEntry] | AppEntry | int:
    if not context.call_sync2(context.s.docker.validate_state, False):
        return _to_entries(filter_list([], filters, options.model_dump()))

    extra = options.extra
    host_ip = extra.get('host_ip')
    if not host_ip:
        try:
            if app.origin.is_tcp_ip_family:
                host_ip = app.origin.loc_addr
        except AttributeError:
            pass

    retrieve_app_schema = extra.get('include_app_schema', False)
    kwargs = {
        'host_ip': host_ip,
        'retrieve_config': extra.get('retrieve_config', False),
        'image_update_cache': context.middleware.call_sync('app.image.op.get_update_cache', True),
        # FIXME: Fix above usage
    }
    if len(filters) == 1 and filters[0][0] in ('id', 'name') and filters[0][1] == '=':
        kwargs['specific_app'] = filters[0][2]

    available_apps_mapping = context.call_sync2(context.s.catalog.train_to_apps_version_mapping)

    apps = list_apps(available_apps_mapping, **kwargs)
    if not retrieve_app_schema:
        return _to_entries(filter_list(apps, filters, options.model_dump()))

    questions_context = context.call_sync2(context.s.catalog.get_normalized_questions_context)
    for app_entry in apps:
        if app_entry['custom_app']:
            version_details = get_version_details()
        else:
            version_details = context.call_sync2(
                context.s.catalog.app_version_details,
                get_installed_app_version_path(app_entry['name'], app_entry['version']),
                questions_context,
            )

        app_entry['version_details'] = version_details

    return _to_entries(filter_list(apps, filters, options.model_dump()))


def get_instance(context: ServiceContext, app_name: str, options: QueryOptions | None = None) -> AppEntry:
    options = options or QueryOptions()
    results = query_apps(context, [['id', '=', app_name]], options)
    if not results:
        raise InstanceNotFound(f'App {app_name} does not exist')
    return results[0]


def get_app_config(context: ServiceContext, app_name: str) -> dict[str, Any]:
    app = get_instance(context, app_name)
    return get_current_app_config(app_name, app.version)
