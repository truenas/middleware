from __future__ import annotations

from typing import TYPE_CHECKING, Any

from catalog_reader.custom_app import get_version_details

from middlewared.api.current import AppDelete, AppEntry
from middlewared.service import CallError, ServiceContext

from .compose_utils import collect_logs, compose_action
from .custom_app_utils import validate_payload
from .ix_apps.lifecycle import get_rendered_template_config_of_app, update_app_config
from .ix_apps.metadata import update_app_metadata
from .ix_apps.setup import setup_install_app_dir
from .resources import delete_internal_resources, remove_failed_resources

if TYPE_CHECKING:
    from middlewared.job import Job


def convert_to_custom_app(context: ServiceContext, job: Job, app_name: str) -> AppEntry:
    app = context.call_sync2(context.s.app.get_instance, app_name)
    if app.custom_app is True:
        raise CallError(f'{app_name!r} is already a custom app')

    rendered_config = get_rendered_template_config_of_app(app_name, app.version)
    if not rendered_config:
        raise CallError(f'No rendered config found for {app_name!r}')

    job.set_progress(10, 'Completed initial validation for conversion of app to custom app')
    # Merge all available compose files into one of the app and hold on to it
    # Do an uninstall of the app and create it again with the new compose file
    # Update metadata to reflect that this is a custom app
    # Finally update collective metadata
    job.set_progress(20, "Removing existing app's docker resources")
    delete_internal_resources(
        context, app_name, app, AppDelete(remove_images=False, remove_ix_volumes=False), None, False,
    )

    return create_custom_app(context, job, {
        'app_name': app_name,
        'custom_compose_config': rendered_config,
        'conversion': True,
    })


def create_custom_app(
    context: ServiceContext, job: Job, data: dict[str, Any], progress_base: int = 0,
) -> AppEntry:
    compose_config = validate_payload(data, 'app_create')
    app_being_converted = data.get('conversion', False)

    def update_progress(percentage_done: int, message: str) -> None:
        job.set_progress(int((100 - progress_base) * (percentage_done / 100)) + progress_base, message)

    update_progress(25, 'Initial validation completed for custom app creation')

    app_name = data['app_name']
    app_version_details = get_version_details()
    version = app_version_details['version']
    try:
        update_progress(35, 'Setting up App directory')
        setup_install_app_dir(app_name, app_version_details, custom_app=True)
        update_app_config(app_name, version, compose_config, custom_app=True)
        update_app_metadata(app_name, app_version_details, migrated=False, custom_app=True)

        if app_being_converted:
            msg = 'App conversion in progress, pulling images'
        else:
            msg = 'App installation in progress, pulling images'
        update_progress(60, msg)
        compose_action(app_name, version, 'up', force_recreate=True, remove_orphans=True)
    except Exception as e:
        assert job.logs_fd is not None
        if logs := collect_logs(app_name, version):
            job.logs_fd.write(f'App installation logs for {app_name}:\n{logs}'.encode())
        else:
            job.logs_fd.write(f'No logs could be retrieved for {app_name!r} installation failure\n'.encode())

        update_progress(
            80,
            'Failure occurred while '
            f'{"converting" if app_being_converted else "installing"} {app_name!r}, cleaning up'
        )

        remove_failed_resources(context, app_name, version)

        raise e from None
    else:
        context.call_sync2(context.s.app.metadata_generate).wait_sync(raise_error=True)
        app_info = context.call_sync2(context.s.app.get_instance, app_name)
        if app_being_converted is False:
            # We only want to send this when a new custom app is being installed, not when an
            # existing app is being converted to a custom app
            context.middleware.send_event('app.query', 'ADDED', id=app_name, fields=app_info.model_dump(by_alias=True))
        job.set_progress(
            100, f'{app_name!r} {"converted to custom app" if app_being_converted else "installed"} successfully'
        )
        return app_info
