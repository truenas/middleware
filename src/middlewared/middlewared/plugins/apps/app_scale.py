from middlewared.api import api_method
from middlewared.api.current import (
    AppStartArgs, AppStartResult, AppStopArgs, AppStopResult, AppRedeployArgs, AppRedeployResult,
)
from middlewared.service import job, Service

from .compose_utils import compose_action
from .ix_apps.query import get_default_workload_values
from .utils import get_app_stop_cache_key


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @api_method(
        AppStopArgs, AppStopResult,
        audit='App: Stopping',
        audit_extended=lambda app_name: app_name,
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_stop_{args[0]}')
    def stop(self, job, app_name):
        """
        Stop `app_name` app.
        """
        app_config = self.middleware.call_sync('app.get_instance', app_name)
        cache_key = get_app_stop_cache_key(app_name)
        try:
            self.middleware.call_sync('cache.put', cache_key, True)
            self.middleware.send_event(
                'app.query', 'CHANGED', id=app_name,
                fields=app_config | {'state': 'STOPPING', 'active_workloads': get_default_workload_values()},
            )
            job.set_progress(20, f'Stopping {app_name!r} app')

            if app_config.get('source') == 'external':
                # For external apps, use direct Docker commands with actual container names
                from .utils import run
                from middlewared.service_exception import CallError
                container_names = [c['id'] for c in app_config.get('active_workloads', {}).get('container_details', [])]
                if not container_names:
                    raise CallError(f'No containers found for external app {app_name!r}')

                for container_name in container_names:
                    cp = run(['docker', 'stop', container_name])
                    if cp.returncode != 0:
                        raise CallError(f'Failed to stop container {container_name!r}: {cp.stderr}')
            else:
                compose_action(
                    app_name, app_config['version'], 'down', remove_orphans=True, remove_images=False, remove_volumes=False,
                )

            job.set_progress(100, f'Stopped {app_name!r} app')
        finally:
            self.middleware.send_event(
                'app.query', 'CHANGED', id=app_name,
                fields=app_config | {'state': 'STOPPED', 'active_workloads': get_default_workload_values()},
            )
            self.middleware.call_sync('cache.pop', cache_key)

    @api_method(
        AppStartArgs, AppStartResult,
        audit='App: Starting',
        audit_extended=lambda app_name: app_name,
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_start_{args[0]}')
    def start(self, job, app_name):
        """
        Start `app_name` app.
        """
        app_config = self.middleware.call_sync('app.get_instance', app_name)
        job.set_progress(20, f'Starting {app_name!r} app')

        if app_config.get('source') == 'external':
            # For external apps, use direct Docker commands with actual container names
            from .utils import run
            from middlewared.service_exception import CallError
            container_names = [c['id'] for c in app_config.get('active_workloads', {}).get('container_details', [])]
            if not container_names:
                raise CallError(f'No containers found for external app {app_name!r}')

            for container_name in container_names:
                cp = run(['docker', 'start', container_name])
                if cp.returncode != 0:
                    raise CallError(f'Failed to start container {container_name!r}: {cp.stderr}')
        else:
            compose_action(app_name, app_config['version'], 'up', force_recreate=True, remove_orphans=True)

        job.set_progress(100, f'Started {app_name!r} app')

    @api_method(
        AppRedeployArgs, AppRedeployResult,
        audit='App: Redeploying',
        audit_extended=lambda app_name: app_name,
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'app_redeploy_{args[0]}')
    async def redeploy(self, job, app_name):
        """
        Redeploy `app_name` app.
        """
        app = await self.middleware.call('app.get_instance', app_name)

        if app.get('source') == 'external':
            # For external apps, restart the containers using actual container names
            from .utils import run
            from middlewared.service_exception import CallError
            container_names = [c['id'] for c in app.get('active_workloads', {}).get('container_details', [])]
            if not container_names:
                raise CallError(f'No containers found for external app {app_name!r}')

            for container_name in container_names:
                cp = run(['docker', 'restart', container_name])
                if cp.returncode != 0:
                    raise CallError(f'Failed to restart container {container_name!r}: {cp.stderr}')
            return

        return await self.middleware.call('app.update_internal', job, app, {'values': {}}, 'Redeployment')
