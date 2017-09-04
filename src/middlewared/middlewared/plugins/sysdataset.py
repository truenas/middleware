from middlewared.schema import accepts
from middlewared.service import ConfigService


class SystemDatasetService(ConfigService):

    @accepts()
    async def config(self):
        return await self.middleware.call('datastore.config', 'system.systemdataset', {'prefix': 'sys_'})
