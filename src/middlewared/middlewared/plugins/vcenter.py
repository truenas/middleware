from middlewared.service import accepts, ConfigService, private, ValidationErrors

from pprint import pprint


class VCenterService(ConfigService):

    class Config:
        datastore = 'vcp.vcenterconfiguration'
        datastore_prefix = 'vc_'
        datastore_extend = ''

    async def do_update(self, data):
        old = await self.config()
        pprint(old)
        return old
