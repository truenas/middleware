from middlewared.async_validators import check_path_resides_within_volume, resolve_hostname, validate_port
from middlewared.service import private, SystemServiceService, ValidationErrors
import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    FtpEntry,
    FtpUpdateArgs, FtpUpdateResult
)


class FTPModel(sa.Model):
    __tablename__ = 'services_ftp'

    id = sa.Column(sa.Integer(), primary_key=True)
    ftp_port = sa.Column(sa.Integer(), default=21)
    ftp_clients = sa.Column(sa.Integer(), default=5)
    ftp_ipconnections = sa.Column(sa.Integer(), default=2)
    ftp_loginattempt = sa.Column(sa.Integer(), default=1)
    ftp_timeout = sa.Column(sa.Integer(), default=600)
    ftp_timeout_notransfer = sa.Column(sa.Integer(), default=300)
    ftp_onlyanonymous = sa.Column(sa.Boolean(), default=False)
    ftp_anonpath = sa.Column(sa.String(255), nullable=True, default=False)
    ftp_onlylocal = sa.Column(sa.Boolean(), default=False)
    ftp_banner = sa.Column(sa.Text())
    ftp_filemask = sa.Column(sa.String(3), default="077")
    ftp_dirmask = sa.Column(sa.String(3), default="022")
    ftp_fxp = sa.Column(sa.Boolean(), default=False)
    ftp_resume = sa.Column(sa.Boolean(), default=False)
    ftp_defaultroot = sa.Column(sa.Boolean(), default=True)
    ftp_ident = sa.Column(sa.Boolean(), default=False)
    ftp_reversedns = sa.Column(sa.Boolean(), default=False)
    ftp_masqaddress = sa.Column(sa.String(120))
    ftp_passiveportsmin = sa.Column(sa.Integer(), default=0)
    ftp_passiveportsmax = sa.Column(sa.Integer(), default=0)
    ftp_localuserbw = sa.Column(sa.Integer(), default=0)
    ftp_localuserdlbw = sa.Column(sa.Integer(), default=0)
    ftp_anonuserbw = sa.Column(sa.Integer(), default=0)
    ftp_anonuserdlbw = sa.Column(sa.Integer(), default=0)
    ftp_tls = sa.Column(sa.Boolean(), default=False)
    ftp_tls_policy = sa.Column(sa.String(120), default="on")
    ftp_tls_opt_allow_client_renegotiations = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_allow_dot_login = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_allow_per_user = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_common_name_required = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_enable_diags = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_export_cert_data = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_no_empty_fragments = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_no_session_reuse_required = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_stdenvvars = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_dns_name_required = sa.Column(sa.Boolean(), default=False)
    ftp_tls_opt_ip_address_required = sa.Column(sa.Boolean(), default=False)
    ftp_ssltls_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    ftp_options = sa.Column(sa.Text())


class FTPService(SystemServiceService):

    class Config:
        service = "ftp"
        datastore = "services.ftp"
        datastore_prefix = "ftp_"
        datastore_extend = "ftp.ftp_extend"
        cli_namespace = "service.ftp"
        role_prefix = "SHARING_FTP"
        entry = FtpEntry

    @private
    async def ftp_extend(self, data):
        if data['ssltls_certificate']:
            data['ssltls_certificate'] = data['ssltls_certificate']['id']
        return data

    @api_method(FtpUpdateArgs, FtpUpdateResult, audit='Update FTP configuration')
    async def do_update(self, data):
        """
        Update ftp service configuration.

        `clients` is an integer value which sets the maximum number of simultaneous clients allowed. It defaults to 32.

        `ipconnections` is an integer value which shows the maximum number of connections per IP address. It defaults
        to 0 which equals to unlimited.

        `timeout` is the maximum number of seconds that proftpd will allow clients to stay connected without receiving
        any data on either the control or data connection.

        `timeout_notransfer` is the maximum number of seconds a client is allowed to spend connected, after
        authentication, without issuing a command which results in creating an active or passive data connection
        (i.e. sending/receiving a file, or receiving a directory listing).

        `onlyanonymous` allows anonymous FTP logins with access to the directory specified by `anonpath`.

        `banner` is a message displayed to local login users after they successfully authenticate. It is not displayed
        to anonymous login users.

        `filemask` sets the default permissions for newly created files which by default are 077.

        `dirmask` sets the default permissions for newly created directories which by default are 077.

        `resume` if set allows FTP clients to resume interrupted transfers.

        `fxp` if set to true indicates that File eXchange Protocol is enabled. Generally it is discouraged as it
        makes the server vulnerable to FTP bounce attacks.

        `defaultroot` when set ensures that for local users, home directory access is only granted if the user
        is a member of group wheel.

        `ident` is a boolean value which when set to true indicates that IDENT authentication is required. If identd
        is not running on the client, this can result in timeouts.

        `masqaddress` is the public IP address or hostname which is set if FTP clients cannot connect through a
        NAT device.

        `localuserbw` is a positive integer value which indicates maximum upload bandwidth in KB/s for local user.
        Default of zero indicates unlimited upload bandwidth ( from the FTP server configuration ).

        `localuserdlbw` is a positive integer value which indicates maximum download bandwidth in KB/s for local user.
        Default of zero indicates unlimited download bandwidth ( from the FTP server configuration ).

        `anonuserbw` is a positive integer value which indicates maximum upload bandwidth in KB/s for anonymous user.
        Default of zero indicates unlimited upload bandwidth ( from the FTP server configuration ).

        `anonuserdlbw` is a positive integer value which indicates maximum download bandwidth in KB/s for anonymous
        user. Default of zero indicates unlimited download bandwidth ( from the FTP server configuration ).

        `tls` is a boolean value which when set indicates that encrypted connections are enabled. This requires a
        certificate to be configured first with the certificate service and the id of certificate is passed on in
        `ssltls_certificate`.

        `tls_policy` defines whether the control channel, data channel, both channels, or neither channel of an FTP
        session must occur over SSL/TLS.

        `tls_opt_enable_diags` is a boolean value when set, logs verbosely. This is helpful when troubleshooting a
        connection.

        `options` is a string used to add proftpd(8) parameters not covered by ftp service.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if not ((new["passiveportsmin"] == 0) == (new["passiveportsmax"] == 0)):
            verrors.add("passiveportsmin", "passiveportsmin and passiveportsmax should be both zero or non-zero")
        if not ((new["passiveportsmin"] == 0 and new["passiveportsmax"] == 0) or
                (new["passiveportsmax"] > new["passiveportsmin"])):
            verrors.add("ftp_update.passiveportsmax", "When specified, should be greater than passiveportsmin")

        if new["onlyanonymous"]:
            if not new["anonpath"]:
                verrors.add("ftp_update.anonpath", "This field is required for anonymous login")
        else:
            # Anonymous is disabled, clear the anonpath
            if new["anonpath"] is not None:
                new["anonpath"] = None

        if new["anonpath"] is not None:
            await check_path_resides_within_volume(
                verrors, self.middleware, "ftp_update.anonpath", new["anonpath"], must_be_dir=True
            )

        if new["tls"]:
            if not new["ssltls_certificate"]:
                verrors.add(
                    "ftp_update.ssltls_certificate",
                    "Please provide a valid certificate id when TLS is enabled"
                )
            else:
                verrors.extend((await self.middleware.call(
                    "certificate.cert_services_validation", new["ssltls_certificate"],
                    "ftp_update.ssltls_certificate", False
                )))

        if new["masqaddress"]:
            await resolve_hostname(self.middleware, verrors, "ftp_update.masqaddress", new["masqaddress"])

        verrors.extend(await validate_port(self.middleware, "ftp_update.port", new["port"], "ftp"))

        verrors.check()

        await self._update_service(old, new)

        if not old['tls'] and new['tls']:
            await self.middleware.call('service.start', 'ssl')

        return new


async def pool_post_import(middleware, pool):
    """
    We don't set up anonymous FTP if pool is not imported yet.
    """
    if pool is None:
        try:
            await middleware.call("etc.generate", "ftp")
        except Exception:
            middleware.logger.debug("Failed to generate ftp configuration file.", exc_info=True)
        finally:
            return

    await middleware.call("service.reload", "ftp")


async def setup(middleware):
    middleware.register_hook("pool.post_import", pool_post_import, sync=True)
