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
                # For external apps, handle both Docker Compose projects and standalone containers
                from .utils import run
                from middlewared.service_exception import CallError

                # Check if this is a Docker Compose project by looking at container labels
                container_details = app_config.get('active_workloads', {}).get('container_details', [])

                if container_details:
                    # Get the first container to check for compose labels
                    from .ix_apps.docker.utils import get_docker_client
                    with get_docker_client() as client:
                        try:
                            first_container = client.containers.get(container_details[0]['id'])
                            compose_config_file = first_container.labels.get('com.docker.compose.project.config_files')
                            compose_working_dir = first_container.labels.get('com.docker.compose.project.working_dir')

                            if compose_config_file and compose_working_dir:
                                # Use docker compose commands
                                cp = run([
                                    'docker', 'compose',
                                    '-f', compose_config_file,
                                    '--project-directory', compose_working_dir,
                                    'stop'
                                ])
                                if cp.returncode != 0:
                                    raise CallError(f'Failed to stop compose project {app_name!r}: {cp.stderr}')
                            else:
                                # Standalone containers - stop each one individually
                                for container in container_details:
                                    cp = run(['docker', 'stop', container['id']])
                                    if cp.returncode != 0:
                                        raise CallError(f'Failed to stop container {container["id"]}: {cp.stderr}')
                        except Exception as e:
                            raise CallError(f'Failed to stop external app {app_name!r}: {e}')
                else:
                    # No active containers - already stopped or not found
                    raise CallError(f'No active containers found for external app {app_name!r}')
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
            # For external apps, handle both Docker Compose projects and standalone containers
            from .utils import run
            from middlewared.service_exception import CallError
            from .ix_apps.docker.utils import get_docker_client, PROJECT_KEY

            # Query Docker for all containers belonging to this app (including stopped ones)
            with get_docker_client() as client:
                try:
                    # For external apps, the app_name could be a compose project name or container name
                    # First, try to find containers with matching compose project label
                    containers = client.containers.list(
                        all=True,
                        filters={'label': f'{PROJECT_KEY}={app_name}'}
                    )

                    if not containers:
                        # If no compose project found, try as a direct container name
                        try:
                            container = client.containers.get(app_name)
                            containers = [container]
                        except Exception:
                            raise CallError(f'No containers found for external app {app_name!r}')

                    # Check if this is a Docker Compose project
                    first_container = containers[0]
                    compose_config_file = first_container.labels.get('com.docker.compose.project.config_files')
                    compose_working_dir = first_container.labels.get('com.docker.compose.project.working_dir')

                    if compose_config_file and compose_working_dir:
                        # Use docker compose commands
                        cp = run([
                            'docker', 'compose',
                            '-f', compose_config_file,
                            '--project-directory', compose_working_dir,
                            'start'
                        ])
                        if cp.returncode != 0:
                            raise CallError(f'Failed to start compose project {app_name!r}: {cp.stderr}')
                    else:
                        # Standalone containers - start each one individually
                        for container in containers:
                            cp = run(['docker', 'start', container.id])
                            if cp.returncode != 0:
                                raise CallError(f'Failed to start container {container.id}: {cp.stderr}')
                except CallError:
                    raise
                except Exception as e:
                    raise CallError(f'Failed to start external app {app_name!r}: {e}')
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
            # For external apps, handle both Docker Compose projects and standalone containers
            from .utils import run
            from middlewared.service_exception import CallError
            from .ix_apps.docker.utils import get_docker_client, PROJECT_KEY

            # Query Docker for all containers belonging to this app
            with get_docker_client() as client:
                try:
                    # For external apps, the app_name could be a compose project name or container name
                    # First, try to find containers with matching compose project label
                    containers = client.containers.list(
                        all=True,
                        filters={'label': f'{PROJECT_KEY}={app_name}'}
                    )

                    if not containers:
                        # If no compose project found, try as a direct container name
                        try:
                            container = client.containers.get(app_name)
                            containers = [container]
                        except Exception:
                            raise CallError(f'No containers found for external app {app_name!r}')

                    # Check if this is a Docker Compose project
                    first_container = containers[0]
                    compose_config_file = first_container.labels.get('com.docker.compose.project.config_files')
                    compose_working_dir = first_container.labels.get('com.docker.compose.project.working_dir')

                    if compose_config_file and compose_working_dir:
                        # Use docker compose commands
                        cp = run([
                            'docker', 'compose',
                            '-f', compose_config_file,
                            '--project-directory', compose_working_dir,
                            'restart'
                        ])
                        if cp.returncode != 0:
                            raise CallError(f'Failed to restart compose project {app_name!r}: {cp.stderr}')
                    else:
                        # Standalone containers - restart each one individually
                        for container in containers:
                            cp = run(['docker', 'restart', container.id])
                            if cp.returncode != 0:
                                raise CallError(f'Failed to restart container {container.id}: {cp.stderr}')
                except CallError:
                    raise
                except Exception as e:
                    raise CallError(f'Failed to restart external app {app_name!r}: {e}')
            return

        return await self.middleware.call('app.update_internal', job, app, {'values': {}}, 'Redeployment')
