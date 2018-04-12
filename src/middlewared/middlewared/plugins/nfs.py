from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List
from middlewared.validators import Range
from middlewared.service import SystemServiceService, ValidationErrors


class NFSService(SystemServiceService):

    class Config:
        service = "nfs"
        datastore_prefix = "nfs_srv_"

    @accepts(Dict(
        'nfs_update',
        Int('servers', validators=[Range(min=1, max=256)]),
        Bool('udp'),
        Bool('allow_nonroot'),
        Bool('v4'),
        Bool('v4_v3owner'),
        Bool('v4_krb'),
        List('bindip', items=[IPAddr('ip')]),
        Int('mountd_port', required=False, validators=[Range(min=1, max=65535)]),
        Int('rpcstatd_port', required=False, validators=[Range(min=1, max=65535)]),
        Int('rpclockd_port', required=False, validators=[Range(min=1, max=65535)]),
        Bool('16'),
        Bool('mountd_log'),
        Bool('statd_lockd_log'),
    ))
    async def update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if not new["v4"] and new["v4_v3owner"]:
            verrors.add("nfs_update.v4_v3owner", "This option requires enabling NFSv4")

        if new["v4_v3owner"] and new["16"]:
            verrors.add("nfs_update.16", "This option is incompatible with NFSv3 ownership model for NFSv4:")

        if verrors:
            raise verrors

        await self._update_service(old, new)

        return new
