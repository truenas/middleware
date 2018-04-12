from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List
from middlewared.validators import Range
from middlewared.service import private, SystemServiceService, ValidationErrors


class NFSService(SystemServiceService):

    class Config:
        service = "nfs"
        datastore_prefix = "nfs_srv_"
        datastore_extend = 'nfs.nfs_extend'

    @private
    def nfs_extend(self, nfs):
        nfs["userd_manage_gids"] = nfs.pop("16")
        return nfs

    @private
    def nfs_compress(self, nfs):
        nfs["16"] = nfs.pop("userd_manage_gids")
        return nfs

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
        Bool('userd_manage_gids'),
        Bool('mountd_log'),
        Bool('statd_lockd_log'),
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if not new["v4"] and new["v4_v3owner"]:
            verrors.add("nfs_update.v4_v3owner", "This option requires enabling NFSv4")

        if new["v4_v3owner"] and new["userd_manage_gids"]:
            verrors.add(
                "nfs_update.userd_manage_gids", "This option is incompatible with NFSv3 ownership model for NFSv4")

        if verrors:
            raise verrors

        self.nfs_compress(new)

        await self._update_service(old, new)

        self.nfs_extend(new)

        return new
