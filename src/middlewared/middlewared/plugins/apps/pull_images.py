from middlewared.api import api_method
from middlewared.api.current import (
    AppOutdatedDockerImagesArgs, AppOutdatedDockerImagesResult, AppPullImagesArgs, AppPullImagesResult,
)
from middlewared.plugins.apps_images.utils import normalize_reference
from middlewared.service import job, private, Service

from .compose_utils import compose_action


class AppService(Service):

    class Config:
        namespace = 'app'
        cli_namespace = 'app'

    @api_method(AppOutdatedDockerImagesArgs, AppOutdatedDockerImagesResult, roles=['APPS_READ'])
    async def outdated_docker_images(self, app_name):
        """
        Returns a list of outdated docker images for the specified app `name`.
        """
        app = await self.middleware.call('app.get_instance', app_name)
        image_update_cache = await self.middleware.call('app.image.op.get_update_cache', True)
        images = []
        for image_tag in app['active_workloads']['images']:
            if image_update_cache.get(normalize_reference(image_tag)['complete_tag']):
                images.append(image_tag)

        return images

    @api_method(
        AppPullImagesArgs, AppPullImagesResult,
        audit='App: Pulling Images for',
        audit_extended=lambda app_name, options=None: app_name,
        roles=['APPS_WRITE']
    )
    @job(lock=lambda args: f'pull_images_{args[0]}')
    def pull_images(self, job, app_name, options):
        """
        Pulls docker images for the specified app `name`.
        """
        app = self.middleware.call_sync('app.get_instance', app_name)
        return self.pull_images_internal(app_name, app, options, job)

    @private
    def pull_images_internal(self, app_name, app, options, job=None):
        job = job or type('dummy_job', (object,), {'set_progress': lambda *args: None})()
        job.set_progress(20, 'Pulling app images')

        compose_action(app_name, app['version'], action='pull', force_pull=True)
        job.set_progress(80 if options['redeploy'] else 100, 'Images pulled successfully')

        # We will update image cache so that it reflects the fact that image has been pulled again
        # We won't really check again here but rather just update the cache directly because we know
        # compose action didn't fail and that means the pull succeeded and we should have the newer version
        # already in the system
        for image_tag in app['active_workloads']['images']:
            self.middleware.call_sync('app.image.op.clear_update_flag_for_tag', image_tag)

        if options['redeploy']:
            self.middleware.call_sync('app.redeploy', app_name).wait_sync(raise_error=True)
            job.set_progress(100, 'App redeployed successfully')
