from middlewared.schema import accepts, Bool, Dict, Dir, Int, Str
from middlewared.validators import Range
from middlewared.service import SystemServiceService


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
        Str('umask'),
        Str('options'),
    ))
    async def update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self._update_service(old, new)

        return new
