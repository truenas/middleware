from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import AppEntry, AppUpdate, QueryOptions
from middlewared.service import ServiceContext

from .compose_utils import compose_action
from .crud import get_instance, update_internal
from .ix_apps.query import get_default_workload_values
from .utils import get_app_stop_cache_key


if TYPE_CHECKING:
    from middlewared.job import Job


def stop_app(context: ServiceContext, job: Job, app_name: str) -> None:
    app = get_instance(context, app_name)
    cache_key = get_app_stop_cache_key(app_name)
    try:
        context.middleware.call_sync('cache.put', cache_key, True)
        context.middleware.send_event(
            'app.query', 'CHANGED', id=app_name,
            fields=app.model_dump() | {'state': 'STOPPING', 'active_workloads': get_default_workload_values()},
        )
        job.set_progress(20, f'Stopping {app_name!r} app')
        compose_action(
            app_name, app.version, 'down', remove_orphans=True, remove_images=False, remove_volumes=False,
        )
        job.set_progress(100, f'Stopped {app_name!r} app')
    finally:
        context.middleware.send_event(
            'app.query', 'CHANGED', id=app_name,
            fields=app.model_dump() | {'state': 'STOPPED', 'active_workloads': get_default_workload_values()},
        )
        context.middleware.call_sync('cache.pop', cache_key)


def start_app(context: ServiceContext, job: Job, app_name: str) -> None:
    app = get_instance(context, app_name)
    job.set_progress(20, f'Starting {app_name!r} app')
    compose_action(app_name, app.version, 'up', force_recreate=True, remove_orphans=True)
    job.set_progress(100, f'Started {app_name!r} app')


def redeploy_app(context: ServiceContext, job: Job, app_name: str) -> AppEntry:
    app = get_instance(context, app_name, QueryOptions(extra={'retrieve_config': True}))
    return update_internal(context, job, app, AppUpdate(), 'Redeployment')
