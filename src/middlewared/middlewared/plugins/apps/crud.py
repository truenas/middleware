from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any, Literal, cast, overload

from catalog_reader.custom_app import get_version_details
from pydantic import ValidationError

from middlewared.api.current import (
    AppCreate,
    AppDelete,
    AppEntry,
    AppUpdate,
    CatalogAppVersionDetails,
    QueryOptions,
)
from middlewared.job import State
from middlewared.service import CallError, InstanceNotFound, ServiceContext, ValidationErrors
from middlewared.utils.filter_list import filter_list

from .compose_utils import collect_logs, compose_action
from .custom_app_ops import create_custom_app
from .custom_app_utils import validate_payload
from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.metadata import get_collective_metadata, update_app_metadata, update_app_metadata_for_portals
from .ix_apps.path import get_installed_app_path, get_installed_app_version_path
from .ix_apps.query import error_app_data, get_default_workload_values, list_apps
from .ix_apps.setup import setup_install_app_dir
from .resources import delete_internal_resources, get_app_volume_ds, remove_failed_resources
from .schema_normalization import normalize_and_validate_values
from .utils import app_version, assert_app_usable, band_progress
from .version_utils import get_latest_version_from_app_versions

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.api.current import QueryOptionsCount, QueryOptionsGet
    from middlewared.job import Job


def apps_being_installed(context: ServiceContext) -> set[str]:
    """
    Names of apps with an installation in flight, read from the in-memory job queue.

    An app's directory is created shortly before its metadata is written to it, so without this an
    install in progress is indistinguishable on disk from an app whose metadata has gone missing.
    """
    installing = set()
    for job in context.middleware.jobs.all().values():
        if job.method_name != 'app.create' or job.state not in (State.WAITING, State.RUNNING) or not job.args:
            continue

        # Depending on how the job was queued, its payload is either the raw dict from the caller
        # or an already validated model
        payload = job.args[0]
        app_name = payload.get('app_name') if isinstance(payload, dict) else getattr(payload, 'app_name', None)
        if app_name:
            installing.add(app_name)

    return installing


def to_app_entry(row: dict[str, Any], retrieve_config: bool) -> AppEntry:
    """
    One row of ``list_apps`` as an entry, or the error entry when the API model cannot describe it.

    A row carries data we do not produce ourselves - every key of the app's metadata file, and the
    workloads docker reports - so a metadata file which was hand edited, or written by a release we
    know nothing about, can hold a key we do not expect or a value of a type we cannot use.
    Reporting such an app the way one with unusable metadata is reported leaves it deletable, where
    letting the validation error escape would take app.query down for every app on the box.
    """
    constructor = cast('type[AppEntry]', getattr(AppEntry, '__query_result_item__', AppEntry))
    try:
        # Validated rather than splatted: yaml mapping keys need not be strings, and `**row` would
        # raise TypeError before the model ever got the chance to reject the key
        return constructor.model_validate(row)
    except ValidationError:
        app_name = row.get('name') or row.get('id')
        if not isinstance(app_name, str) or not app_name:
            # There is no entry we could report an app we cannot even name as. A row of this shape
            # only comes of a query which selected neither `name` nor `id`.
            raise

    # Its real workloads keep the ports and volumes the app is still holding on to visible to
    # conflict checks, where we can describe them
    try:
        return constructor.model_validate(error_app_data(
            app_name, 'METADATA_INCOMPLETE', row.get('active_workloads') or {}, retrieve_config,
        ))
    except ValidationError:
        # The workloads are themselves what cannot be described. Everything else in the error entry
        # is a constant, so reporting no workloads at all always leaves a deletable app.
        return constructor.model_validate(error_app_data(
            app_name, 'METADATA_INCOMPLETE', get_default_workload_values(), retrieve_config,
        ))


def to_app_entries(
    result: list[dict[str, Any]] | dict[str, Any] | int, retrieve_config: bool,
) -> list[AppEntry] | AppEntry | int:
    if isinstance(result, int):
        return result
    if isinstance(result, dict):
        return to_app_entry(result, retrieve_config)

    return [to_app_entry(row, retrieve_config) for row in result]


@overload
def query_apps(  # type: ignore[overload-overlap]
    context: ServiceContext, filters: list[Any], options: QueryOptionsCount, app: App | None = None,
) -> int: ...


@overload
def query_apps(  # type: ignore[overload-overlap]
    context: ServiceContext, filters: list[Any], options: QueryOptionsGet, app: App | None = None,
) -> AppEntry: ...


@overload
def query_apps(
    context: ServiceContext, filters: list[Any], options: QueryOptions, app: App | None = None,
) -> list[AppEntry]: ...


def query_apps(
    context: ServiceContext, filters: list[Any], options: QueryOptions, app: App | None = None,
) -> list[AppEntry] | AppEntry | int:
    extra = options.extra
    retrieve_config = extra.get('retrieve_config', False)
    if not context.call_sync2(context.s.docker.validate_state, False):
        return to_app_entries(filter_list([], filters, options.model_dump()), retrieve_config)

    host_ip = extra.get('host_ip')
    if app is not None and not host_ip:
        if app.origin.is_tcp_ip_family:
            host_ip = app.origin.loc_addr

    retrieve_app_schema = extra.get('include_app_schema', False)
    kwargs = {
        'host_ip': host_ip,
        'retrieve_config': retrieve_config,
        'image_update_cache': context.call_sync2(context.s.app.image.get_update_cache, True),
        'installing': apps_being_installed(context),
    }
    if len(filters) == 1 and filters[0][0] in ('id', 'name') and filters[0][1] == '=':
        kwargs['specific_app'] = filters[0][2]

    available_apps_mapping = context.call_sync2(context.s.catalog.train_to_apps_version_mapping)

    apps = list_apps(available_apps_mapping, **kwargs)
    if not retrieve_app_schema:
        return to_app_entries(filter_list(apps, filters, options.model_dump()), retrieve_config)

    questions_context = context.call_sync2(context.s.catalog.get_normalized_questions_context)
    for app_entry in apps:
        if app_entry['custom_app']:
            version_details = get_version_details()
        elif not app_entry.get('version'):
            # We cannot locate the app's version directory, so there is no schema to report
            continue
        else:
            version_details = context.call_sync2(
                context.s.catalog.app_version_details,
                get_installed_app_version_path(app_entry['name'], app_entry['version']),
                questions_context,
            )

        app_entry['version_details'] = version_details

    return to_app_entries(filter_list(apps, filters, options.model_dump()), retrieve_config)


def get_instance(context: ServiceContext, app_name: str, options: QueryOptions | None = None) -> AppEntry:
    options = options or QueryOptions()
    results = query_apps(context, [['id', '=', app_name]], QueryOptions(extra=options.extra))
    if not results:
        raise InstanceNotFound(f'App {app_name} does not exist')
    return results[0]


def get_usable_instance(context: ServiceContext, app_name: str, options: QueryOptions | None = None) -> AppEntry:
    """
    Like ``get_instance`` but refuses apps we cannot manage. Deletion is the only operation that
    should be using ``get_instance`` directly.
    """
    app = get_instance(context, app_name, options)
    assert_app_usable(app)
    return app


def get_app_config(context: ServiceContext, app_name: str) -> dict[str, Any]:
    app = get_usable_instance(context, app_name)
    return get_current_app_config(app_name, app_version(app))


def create_app(context: ServiceContext, job: Job, data: AppCreate) -> AppEntry:
    context.call_sync2(context.s.docker.validate_state)

    if query_apps(context, [['id', '=', data.app_name]], QueryOptions()):
        raise CallError(f'Application with name {data.app_name} already exists', errno=errno.EEXIST)

    if data.custom_app:
        return create_custom_app(context, job, data.model_dump(expose_secrets=True))

    verrors = ValidationErrors()
    if not data.catalog_app:
        verrors.add('app_create.catalog_app', 'This field is required')
    verrors.check()
    assert data.catalog_app is not None

    app_name = data.app_name
    complete_app_details = context.call_sync2(
        context.s.catalog.get_app_details,
        data.catalog_app,
        CatalogAppVersionDetails(train=data.train),
    )
    version = data.version
    if version == 'latest':
        version = get_latest_version_from_app_versions(complete_app_details.versions)

    if version not in complete_app_details.versions:
        raise CallError(f'Version {version} not found in {data.catalog_app} app', errno=errno.ENOENT)

    app_metadata = complete_app_details.versions[version].get('app_metadata') or {}
    annotations = app_metadata.get('annotations') or {}
    if annotations.get('disallow_multiple_instances'):
        # We will like to raise validation error if multiple instances of the app in question cannot
        # be installed at the same time
        catalog_app = data.catalog_app
        train = data.train
        for installed_app in get_collective_metadata().values():
            # An entry of the collective metadata is whatever yaml parsed it as, so one broken app
            # must not stand in the way of installing an unrelated one
            if not isinstance(installed_app, dict) or not isinstance(installed_app.get('metadata'), dict):
                continue

            installed_app_metadata = installed_app['metadata']
            if installed_app_metadata.get('name') == catalog_app and installed_app_metadata.get('train') == train:
                verrors.add(
                    'app_create.catalog_app',
                    f'{catalog_app!r} app does not allow multiple instances',
                )
                verrors.check()

    return create_internal(context, job, app_name, version, data.values.get_secret_value(), complete_app_details)


@overload
def create_internal(
    context: ServiceContext, job: Job, app_name: str, version: str,
    user_values: dict[str, Any], complete_app_details: Any,
    dry_run: Literal[True], migrated_app: bool = False,
) -> None: ...


@overload
def create_internal(
    context: ServiceContext, job: Job, app_name: str, version: str,
    user_values: dict[str, Any], complete_app_details: Any,
    dry_run: Literal[False] = False, migrated_app: bool = False,
) -> AppEntry: ...


def create_internal(
    context: ServiceContext, job: Job, app_name: str, version: str,
    user_values: dict[str, Any], complete_app_details: Any,
    dry_run: bool = False, migrated_app: bool = False,
) -> AppEntry | None:
    app_version_details = complete_app_details.versions[version]
    context.call_sync2(context.s.catalog.version_supported_error_check, app_version_details)

    app_volume_ds_exists = bool(get_app_volume_ds(context, app_name))
    # The idea is to validate the values provided first and if it passes our validation test, we
    # can move forward with setting up the datasets and installing the catalog item
    new_values = context.run_coroutine(normalize_and_validate_values(
        context, app_version_details, user_values, False, get_installed_app_path(app_name), None, dry_run is False
    ))

    job.set_progress(25, 'Initial Validation completed')

    # Now that we have completed validation for the app in question wrt values provided,
    # we will now perform the following steps
    # 1) Create relevant dir for app
    # 2) Copy app version into app dir
    # 3) Have docker compose deploy the app in question

    assert job.logs_fd is not None
    try:
        setup_install_app_dir(app_name, app_version_details)
        app_version_details = context.call_sync2(
            context.s.catalog.app_version_details,
            get_installed_app_version_path(app_name, version),
        )
        new_values = add_context_to_values(app_name, new_values, app_version_details['app_metadata'], install=True)
        update_app_config(app_name, version, new_values)
        update_app_metadata(app_name, app_version_details, migrated_app)
        context.call_sync2(context.s.app.metadata_generate).wait_sync(raise_error=True)
        entry = get_instance(context, app_name)
        context.middleware.send_event('app.query', 'ADDED', id=app_name, fields=entry.model_dump())

        job.set_progress(60, 'App installation in progress, pulling images')
        if dry_run is False:
            compose_action(
                app_name, version, 'up', force_recreate=True, remove_orphans=True,
                progress_callback=band_progress(job, 60, 95), job=job,
            )
    except Exception as e:
        job.set_progress(80, f'Failure occurred while installing {app_name!r}, cleaning up')
        if logs := collect_logs(app_name, version):
            job.logs_fd.write(f'App installation logs for {app_name}:\n{logs}'.encode())
        else:
            job.logs_fd.write(f'No logs could be retrieved for {app_name!r} installation failure\n'.encode())
        remove_failed_resources(context, app_name, version, app_volume_ds_exists is False)
        context.middleware.send_event('app.query', 'REMOVED', id=app_name)
        raise e from None
    else:
        if dry_run is False:
            job.set_progress(100, f'{app_name!r} installed successfully')
            return get_instance(context, app_name)
        return None


def update_app(context: ServiceContext, job: Job, app_name: str, data: AppUpdate) -> AppEntry:
    app = get_usable_instance(context, app_name, QueryOptions(extra={'retrieve_config': True}))
    app = update_internal(context, job, app, data, trigger_compose=app.state != 'STOPPED')
    context.call_sync2(context.s.app.metadata_generate).wait_sync(raise_error=True)
    return app


def update_internal(
    context: ServiceContext, job: Job, app: AppEntry,
    data: AppUpdate, progress_keyword: str = 'Update', trigger_compose: bool = True,
) -> AppEntry:
    app_name = app.id
    version = app_version(app)
    if app.custom_app:
        if progress_keyword == 'Update':
            new_values = validate_payload(data.model_dump(expose_secrets=True), 'app_update')
        else:
            new_values = get_current_app_config(app_name, version)
    else:
        config = get_current_app_config(app_name, version)
        config.update(data.values.get_secret_value())
        app_version_details = context.call_sync2(
            context.s.catalog.app_version_details, get_installed_app_version_path(app_name, version)
        )

        new_values = context.run_coroutine(normalize_and_validate_values(
            context, app_version_details, config, True, get_installed_app_path(app_name), app,
        ))
        new_values = add_context_to_values(app_name, new_values, app.metadata, update=True)

    job.set_progress(25, 'Initial Validation completed')

    update_app_config(app_name, version, new_values, custom_app=app.custom_app)
    if app.custom_app is False:
        # TODO: Eventually we would want this to be executed for custom apps as well
        update_app_metadata_for_portals(app_name, version)
    job.set_progress(60, 'Configuration updated')
    context.middleware.send_event(
        'app.query', 'CHANGED', id=app_name, fields=get_instance(context, app_name).model_dump()
    )
    if trigger_compose:
        job.set_progress(70, 'Updating docker resources')
        compose_action(
            app_name, version, 'up', force_recreate=True, remove_orphans=True,
            progress_callback=band_progress(job, 70, 99), job=job,
        )

    job.set_progress(100, f'{progress_keyword} completed for {app_name!r}')
    return get_instance(context, app_name)


def delete_app(context: ServiceContext, job: Job, app_name: str, options: AppDelete) -> Literal[True]:
    app_config = get_instance(context, app_name)
    if options.force_remove_custom_app and not app_config.custom_app and app_config.state != 'ERROR':
        # A broken app always reports itself as not being a custom app because we cannot tell either
        # way, so the flag must not stand in the way of removing it
        raise CallError('`force_remove_custom_app` flag is only valid for a custom app', errno=errno.EINVAL)

    return delete_internal_resources(context, app_name, app_config, options, job)
