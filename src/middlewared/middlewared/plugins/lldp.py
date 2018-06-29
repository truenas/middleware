from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import SystemServiceService


class LLDPService(SystemServiceService):
    class Config:
        service = 'lldp'
        datastore_prefix = 'lldp_'

    @accepts(Dict(
        'lldp_update',
        Bool('intdesc'),
        Str('country'),
        Str('location'),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self._update_service(old, new)

        return new
