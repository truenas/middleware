from middlewared.schema import accepts, Dict, Ref, returns, Str
from middlewared.service import filterable, filterable_returns, Service
from middlewared.utils import filter_list


class AppsIxVolumeService(Service):

    class Config:
        namespace = 'app.ix_volume'
        event_send = False
        cli_namespace = 'app.ix_volume'

    @filterable(roles=['APPS_READ'])
    @filterable_returns(Dict())
    async def query(self, filters, options):
        """
        Query ix-volumes with `filters` and `options`.
        """
        if not await self.middleware.call('docker.state.validate', False):
            return filter_list([], filters, options)

        docker_pool = (await self.middleware.call('docker.config'))['pool']

