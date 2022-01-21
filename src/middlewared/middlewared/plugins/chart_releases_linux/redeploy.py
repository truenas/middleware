from middlewared.schema import accepts, Str, Ref, returns
from middlewared.service import job, Service


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
        update_job = await self.middleware.call('chart.release.update', release_name, {'values': {}})
        return await job.wrap(update_job)
