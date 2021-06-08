from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import accepts, Bool, Dict, Dir, Int, Patch, Str
from middlewared.validators import IpAddress
from middlewared.service import SystemServiceService, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.validators import Match, Port


class TFTPModel(sa.Model):
    __tablename__ = 'services_tftp'

    id = sa.Column(sa.Integer(), primary_key=True)
    tftp_directory = sa.Column(sa.String(255))
    tftp_newfiles = sa.Column(sa.Boolean(), default=False)
    tftp_port = sa.Column(sa.Integer(), default=21)
    tftp_username = sa.Column(sa.String(120), default="nobody")
    tftp_umask = sa.Column(sa.String(120), default='022')
    tftp_options = sa.Column(sa.String(120))
    tftp_host = sa.Column(sa.String(120), default="0.0.0.0")


class TFTPService(SystemServiceService):

    class Config:
        service = "tftp"
        datastore_prefix = "tftp_"
        cli_namespace = "service.tftp"

    ENTRY = Dict(
        'tftp_entry',
        Bool('newfiles', required=True),
        Str('directory', required=True),
        Str('host', validators=[IpAddress()], required=True),
        Int('port', validators=[Port()], required=True),
        Str('options', required=True),
        Str('umask', required=True, validators=[Match(r'^[0-7]{3}$')]),
        Str('username', required=True),
        Int('id', required=True),
    )

    @accepts(Patch(
        'tftp_entry', 'tftp_update',
        ('rm', {'name': 'id'}),
        ('replace', Dir('directory')),
        ('attr', {'update': True}),
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
