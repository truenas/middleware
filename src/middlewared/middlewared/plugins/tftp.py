from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import accepts, Bool, Dict, Dir, Int, Str
from middlewared.validators import IpAddress
from middlewared.service import SystemServiceService, ValidationErrors
from middlewared.validators import Match, Port


class TFTPService(SystemServiceService):

    class Config:
        service = "tftp"
        datastore_prefix = "tftp_"

    @accepts(Dict(
        'tftp_update',
        Bool('newfiles'),
        Dir('directory'),
        Str('host', validators=[IpAddress()]),
        Int('port', validators=[Port()]),
        Str('options'),
        Str('umask', validators=[Match(r"^[0-7]{3}$")]),
        Str('username'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update TFTP Service Configuration.

        `newfiles` when set enables network devices to send files to the system.

        `username` sets the user account which will be used to access `directory`. It should be ensured `username`
        has access to `directory`.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new["directory"]:
            await check_path_resides_within_volume(verrors, self.middleware, "tftp_update.directory", new["directory"])

        if verrors:
            raise verrors

        await self._update_service(old, new)

        return await self.config()
