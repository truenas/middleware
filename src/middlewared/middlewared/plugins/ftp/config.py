from typing import Any

from middlewared.api.current import FTPEntry, FTPUpdate
from middlewared.async_validators import check_path_resides_within_volume, resolve_hostname, validate_port
from middlewared.service import SystemServicePart, ValidationErrors
import middlewared.sqlalchemy as sa


class FTPModel(sa.Model):
    __tablename__ = "services_ftp"

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
    ftp_ssltls_certificate_id = sa.Column(sa.ForeignKey("system_certificate.id"), index=True, nullable=True)
    ftp_options = sa.Column(sa.Text())


class FTPServicePart(SystemServicePart[FTPEntry]):
    _datastore = "services.ftp"
    _datastore_prefix = "ftp_"
    _entry = FTPEntry
    _service = "ftp"

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        if data["ssltls_certificate"]:
            data["ssltls_certificate"] = data["ssltls_certificate"]["id"]
        return data

    async def do_update(self, data: FTPUpdate) -> FTPEntry:
        old = await self.config()
        new = old.updated(data)

        await self._validate(new)

        update = new.model_dump()
        update.pop("id", None)
        if not new.onlyanonymous:
            update["anonpath"] = None

        await self._update_service(old.id, update)

        if not old.tls and new.tls:
            await (await self.call2(self.s.service.control, "START", "ssl")).wait(raise_error=True)

        return await self.config()

    async def _validate(self, new: FTPEntry) -> None:
        verrors = ValidationErrors()

        if (new.passiveportsmin == 0) != (new.passiveportsmax == 0):
            verrors.add("passiveportsmin", "passiveportsmin and passiveportsmax should be both zero or non-zero")
        if not ((new.passiveportsmin == 0 and new.passiveportsmax == 0) or (new.passiveportsmax > new.passiveportsmin)):
            verrors.add("ftp_update.passiveportsmax", "When specified, should be greater than passiveportsmin")

        if new.onlyanonymous and not new.anonpath:
            verrors.add("ftp_update.anonpath", "This field is required for anonymous login")

        anonpath = new.anonpath if new.onlyanonymous else None
        if anonpath is not None:
            await check_path_resides_within_volume(
                verrors, self.middleware, "ftp_update.anonpath", anonpath, must_be_dir=True
            )

        if new.tls:
            cert_id = new.ssltls_certificate
            if not cert_id:
                verrors.add(
                    "ftp_update.ssltls_certificate", "Please provide a valid certificate id when TLS is enabled"
                )
            else:
                cert_verrors = await self.call2(
                    self.s.certificate.cert_services_validation,
                    cert_id,
                    "ftp_update.ssltls_certificate",
                    False,
                )
                if cert_verrors:
                    verrors.extend(cert_verrors)

        if new.masqaddress:
            await resolve_hostname(self.middleware, verrors, "ftp_update.masqaddress", new.masqaddress)

        verrors.extend(await validate_port(self.middleware, "ftp_update.port", new.port, "ftp"))

        verrors.check()
