from middlewared.async_validators import check_path_resides_within_volume, resolve_hostname
from middlewared.schema import accepts, Bool, Dict, Dir, Int, Str
from middlewared.validators import Exact, Match, Or, Range
from middlewared.service import SystemServiceService, ValidationErrors


class FTPService(SystemServiceService):

    class Config:
        service = "ftp"
        datastore_prefix = "ftp_"

    @accepts(Dict(
        'ftp_update',
        Int('port', validators=[Range(min=1, max=65535)]),
        Int('clients', validators=[Range(min=1, max=10000)]),
        Int('ipconnections', validators=[Range(min=0, max=1000)]),
        Int('loginattempt', validators=[Range(min=0, max=1000)]),
        Int('timeout', validators=[Range(min=0, max=10000)]),
        Bool('rootlogin'),
        Bool('onlyanonymous'),
        Dir('anonpath', null=True),
        Bool('onlylocal'),
        Str('banner'),
        Str('filemask', validators=[Match(r"^[0-7]{3}$")]),
        Str('dirmask', validators=[Match(r"^[0-7]{3}$")]),
        Bool('fxp'),
        Bool('resume'),
        Bool('defaultroot'),
        Bool('ident'),
        Bool('reversedns'),
        Str('masqaddress'),
        Int('passiveportsmin', validators=[Or(Exact(0), Range(min=1024, max=65535))]),
        Int('passiveportsmax', validators=[Or(Exact(0), Range(min=1024, max=65535))]),
        Int('localuserbw', validators=[Range(min=0)]),
        Int('localuserdlbw', validators=[Range(min=0)]),
        Int('anonuserbw', validators=[Range(min=0)]),
        Int('anonuserdlbw', validators=[Range(min=0)]),
        Bool('tls'),
        Str('tls_policy', enum=["on", "off", "data", "!data", "auth", "ctrl",
                                "ctrl+data", "ctrl+!data", "auth+data", "auth+!data"]),
        Bool('tls_opt_allow_client_renegotiations'),
        Bool('tls_opt_allow_dot_login'),
        Bool('tls_opt_allow_per_user'),
        Bool('tls_opt_common_name_required'),
        Bool('tls_opt_enable_diags'),
        Bool('tls_opt_export_cert_data'),
        Bool('tls_opt_no_cert_request'),
        Bool('tls_opt_no_empty_fragments'),
        Bool('tls_opt_no_session_reuse_required'),
        Bool('tls_opt_stdenvvars'),
        Bool('tls_opt_dns_name_required'),
        Bool('tls_opt_ip_address_required'),
        Int('ssltls_certificate', null=True),
        Str('options'),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if not ((new["passiveportsmin"] == 0) == (new["passiveportsmax"] == 0)):
            verrors.add("passiveportsmin", "passiveportsmin and passiveportsmax should be both zero or non-zero")
        if not ((new["passiveportsmin"] == 0 and new["passiveportsmax"] == 0) or
                (new["passiveportsmax"] > new["passiveportsmin"])):
            verrors.add("ftp_update.passiveportsmax", "When specified, should be greater than passiveportsmin")

        if new["onlyanonymous"] and not new["anonpath"]:
            verrors.add("ftp_update.anonpath", "This field is required for anonymous login")

        if new["anonpath"]:
            await check_path_resides_within_volume(verrors, self.middleware, "ftp_update.anonpath", new["anonpath"])

        if new["tls"] and new["ssltls_certificate"] == 0:
            verrors.add("ftp_update.ssltls_certificate", "This field is required when TLS is enabled")

        if new["masqaddress"]:
            await resolve_hostname(self.middleware, verrors, "ftp_update.masqaddress", new["masqaddress"])

        if verrors:
            raise verrors

        await self._update_service(old, new)

        if not old['tls'] and new['tls']:
            await self.middleware.call('service._start_ssl', 'proftpd')

        return new
