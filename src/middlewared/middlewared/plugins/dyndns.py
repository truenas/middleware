from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import SystemServiceService, private


class DynDNSService(SystemServiceService):

    class Config:
        service = "dynamicdns"
        datastore_extend = "dyndns.dyndns_extend"
        datastore_prefix = "ddns_"

    @private
    async def dyndns_extend(self, dyndns):
        dyndns["password"] = await self.middleware.call("notifier.pwenc_decrypt", dyndns["password"])
        dyndns["domain"] = dyndns["domain"].split()
        return dyndns

    @accepts(Dict(
        'dyndns_update',
        Str('provider'),
        Bool('checkip_ssl'),
        Str('checkip_server'),
        Str('checkip_path'),
        Bool('ssl'),
        Str('custom_ddns_server'),
        Str('custom_ddns_path'),
        List('domain', items=[Str('domain')]),
        Str('username'),
        Str('password'),
        Int('period'),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        new["domain"] = " ".join(new["domain"])
        new["password"] = await self.middleware.call("notifier.pwenc_encrypt", new["password"])

        await self._update_service(old, new)

        await self.dyndns_extend(new)

        return new
