from middlewared.schema import accepts, Str, returns
from middlewared.service import CallError, job, Service

from .compose_utils import compose_action


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @accepts(Str('app_name'))
    @returns()
    @job(lock=lambda args: f'app_stop_{args[0]}')
    def stop(self, job, app_name):
        """
        Stop `app_name` app.
        """
        app_config = self.middleware.call_sync('app.get_instance', app_name)
        job.set_progress(20, f'Stopping {app_name!r} app')
        compose_action(
            app_name, app_config['version'], 'down', remove_orphans=True, remove_images=False, remove_volumes=False,
        )
        job.set_progress(100, f'Stopped {app_name!r} app')

    @accepts(Str('app_name'))
    @returns()
    @job(lock=lambda args: f'app_start_{args[0]}')
    def start(self, job, app_name):
        """
        Start `app_name` app.
        """
        app_config = self.middleware.call_sync('app.get_instance', app_name)
        job.set_progress(20, f'Starting {app_name!r} app')
        compose_action(app_name, app_config['version'], 'up', force_recreate=True, remove_orphans=True)
        job.set_progress(100, f'Started {app_name!r} app')

    @accepts(Str('app_name'))
    @returns()
    @job(lock=lambda args: f'app_redeploy_{args[0]}')
    async def redeploy(self, job, app_name):
        """
        Redeploy `app_name` app.
        """
        app = await self.middleware.call('app.get_instance', app_name)
        return await self.middleware.call('app.update_internal', job, app, {'values': {}}, 'Redeployment')
