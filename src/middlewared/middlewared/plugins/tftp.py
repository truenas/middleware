from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import accepts, Bool, Dict, Dir, Int, Str
from middlewared.validators import Match, Range
from middlewared.service import SystemServiceService, ValidationErrors


class TFTPService(SystemServiceService):

    class Config:
        service = "tftp"
        datastore_prefix = "tftp_"

    @accepts(Dict(
        'tftp_update',
        Dir('directory'),
        Bool('newfiles'),
        Int('port', validators=[Range(min=1, max=65535)]),
        Str('username'),
        Str('umask', validators=[Match(r"^[0-7]{3}$")]),
        Str('options'),
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new["directory"]:
            await check_path_resides_within_volume(verrors, self.middleware, "tftp_update.directory", new["directory"])

        if verrors:
            raise verrors

        await self._update_service(old, new)

        return new
