import errno
import os

from middlewared.schema import accepts, Str, Ref, returns
from middlewared.service import CallError, job, Service

from .utils import add_context_to_configuration, CONTEXT_KEY_NAME, get_action_context


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts(Str('release_name'))
    @returns(Ref('chart_release_entry'))
    @job(lock=lambda args: f'chart_release_redeploy_{args[0]}')
    async def redeploy(self, job, release_name):
        """
        Redeploy will initiate a rollout of new pods according to upgrade strategy defined by the chart release
        workloads. A good example for redeploying is updating kubernetes pods with an updated container image.
        """
        release = await self.middleware.call('chart.release.get_instance', release_name)
        chart_path = os.path.join(release['path'], 'charts', release['chart_metadata']['version'])
        if not os.path.exists(chart_path):
            raise CallError(
                f'Unable to locate {chart_path!r} chart version for redeploying {release!r} chart release',
                errno=errno.ENOENT
            )

        config = add_context_to_configuration(release['config'], {
            CONTEXT_KEY_NAME: {
                **get_action_context(release_name),
                'operation': 'UPDATE',
                'isUpdate': True,
            }
        })
        await self.middleware.call('chart.release.helm_action', release_name, chart_path, config, 'update')

        job.set_progress(90, 'Syncing secrets for chart release')
        await self.middleware.call('chart.release.sync_secrets_for_release', release_name)
        await self.middleware.call('chart.release.refresh_events_state', release_name)
        job.set_progress(100, f'Successfully redeployed {release_name!r} chart release')

        return await self.middleware.call('chart.release.get_instance', release_name)
