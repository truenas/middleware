from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import accepts, Bool, Dict, Dir, Int, List, Str
from middlewared.validators import IpAddress, Range
from middlewared.service import SystemServiceService, ValidationErrors


class AFPService(SystemServiceService):

    class Config:
        service = "afp"
        datastore_prefix = "afp_srv_"

    @accepts(Dict(
        'afp_update',
        Bool('guest'),
        Str('guest_user'),
        List('bindip', items=[Str('ip', validators=[IpAddress()])]),
        Int('connections_limit', validators=[Range(min=1, max=65535)]),
        Dir('dbpath'),
        Str('global_aux'),
        Str('map_acls', enum=["rights", "mode", "none"]),
        Str('chmod_request', enum=["preserve", "simple", "ignore"]),
    ), Bool('dry_run'))
    async def update(self, data, dry_run=False):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new["dbpath"]:
            await check_path_resides_within_volume(verrors, self.middleware, "afp_update.dbpath", new["dbpath"])

        if verrors:
            raise verrors

        if not dry_run:
            await self._update_service(old, new)

        return new
