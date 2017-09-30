from middlewared.schema import accepts, Bool, Dict, Dir, Int, List, Str
from middlewared.validators import IpAddress, Range
from middlewared.service import SystemServiceService, ValidationErrors


class AFPService(SystemServiceService):

    service_name = "afp"
    key_prefix = "afp_srv_"

    @accepts(Dict(
        'afp_update',
        Bool('guest'),
        Str('guest_user'),
        List('bindip', items=[Str('ip', validators=[IpAddress()])]),
        Int('connections_limit', validators=[Range(min=1, max=65535)]),
        Bool('homedir_enable'),
        Dir('homedir'),
        Str('homename'),
        Bool('hometimemachine'),
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

        if new["homedir_enable"] and not new["homedir"]:
            verrors.add("afp_update.homedir", "This field is required for \"Home directories\".")

        if not new["homedir_enable"] and new["homedir"]:
            verrors.add("afp_update.homedir_enable", "This field is required for \"Home directories\".")

        if verrors:
            raise verrors

        if not dry_run:
            await self._update_service(old, new)

        return new
