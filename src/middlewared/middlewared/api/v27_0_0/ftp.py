from typing import Annotated, Literal

from pydantic import Field, field_validator, ValidationInfo

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    single_argument_args,
    UnixPerm
)

__all__ = ["FTPEntry",
           "FTPUpdateArgs", "FTPUpdateResult"]

TLS_PolicyOptions = Literal[
    "", "on", "off", "data", "!data", "auth", "ctrl", "ctrl+data", "ctrl+!data", "auth+data", "auth+!data"
]


class FTPEntry(BaseModel):
    id: int = Field(description="Placeholder identifier.  Not used as there is only one.")
    port: Annotated[int, Field(ge=1, le=65535)] = Field(
        description="TCP port number on which the FTP service listens for incoming connections.",
    )
    clients: Annotated[int, Field(ge=1, le=10000)] = Field(
        description="Maximum number of simultaneous client connections allowed.",
    )
    ipconnections: Annotated[int, Field(ge=0, le=1000)] = Field(
        description="Maximum number of connections allowed from a single IP address. 0 means unlimited.",
    )
    loginattempt: Annotated[int, Field(ge=0, le=1000)] = Field(
        description="Maximum number of failed login attempts before blocking an IP address. 0 disables this limit.",
    )
    timeout: Annotated[int, Field(ge=0, le=10000)] = Field(
        description="Idle timeout in seconds before disconnecting inactive clients. 0 disables timeout.",
    )
    timeout_notransfer: Annotated[int, Field(ge=0, le=10000)] = Field(
        description="Timeout in seconds for clients that connect but do not transfer data. 0 disables timeout.",
    )
    onlyanonymous: bool = Field(
        description="Whether to allow only anonymous FTP access, disabling authenticated user login.",
    )
    anonpath: str | None = Field(
        description="Filesystem path for anonymous FTP users. `null` to use the default anonymous FTP directory.",
    )
    onlylocal: bool = Field(
        description="Whether to allow only local system users to login, disabling anonymous access.",
    )
    banner: str = Field(description="Welcome message displayed to FTP clients upon connection.")
    filemask: UnixPerm = Field(description="Default Unix permissions (umask) for files created by FTP users.")
    dirmask: UnixPerm = Field(description="Default Unix permissions (umask) for directories created by FTP users.")
    fxp: bool = Field(description="Whether to enable File eXchange Protocol (FXP) for server-to-server transfers.")
    resume: bool = Field(description="Whether to allow clients to resume interrupted file transfers.")
    defaultroot: bool = Field(description="Whether to restrict users to their home directories (chroot jail).")
    ident: bool = Field(description="Whether to perform RFC 1413 ident lookups on connecting clients.")
    reversedns: bool = Field(description="Whether to perform reverse DNS lookups on client IP addresses for logging.")
    masqaddress: str = Field(
        description="Public IP address to advertise to clients for passive mode connections when behind NAT.",
    )
    passiveportsmin: int = Field(
        description="Minimum port number for passive mode data connections. Must be 0 or between 1024-65535.",
    )
    passiveportsmax: int = Field(
        description="Maximum port number for passive mode data connections. Must be 0 or between 1024-65535.",
    )
    localuserbw: Annotated[int, Field(ge=0)] = Field(
        description="Maximum upload bandwidth in KiB/s for local users. 0 means unlimited.",
    )
    localuserdlbw: Annotated[int, Field(ge=0)] = Field(
        description="Maximum download bandwidth in KiB/s for local users. 0 means unlimited.",
    )
    anonuserbw: Annotated[int, Field(ge=0)] = Field(
        description="Maximum upload bandwidth in KiB/s for anonymous users. 0 means unlimited.",
    )
    anonuserdlbw: Annotated[int, Field(ge=0)] = Field(
        description="Maximum download bandwidth in KiB/s for anonymous users. 0 means unlimited.",
    )
    tls: bool = Field(description="Whether to enable TLS/SSL encryption for FTP connections.")
    tls_policy: TLS_PolicyOptions = Field(
        description=(
            "TLS policy for connections. Values include: `\"on\"` (required), `\"off\"` (disabled), `\"data\"` (data "
            "only), `\"auth\"` (authentication only), `\"ctrl\"` (control only), or combinations with `+` and `!` "
            "modifiers."
        ),
    )
    tls_opt_allow_client_renegotiations: bool = Field(
        description="Whether to allow TLS clients to initiate renegotiation of the TLS connection.",
    )
    tls_opt_allow_dot_login: bool = Field(
        description="Whether to allow .ftpaccess files to override TLS requirements for specific users.",
    )
    tls_opt_allow_per_user: bool = Field(description="Whether to allow per-user TLS configuration overrides.")
    tls_opt_common_name_required: bool = Field(
        description="Whether to require client certificates to have a Common Name field.",
    )
    tls_opt_enable_diags: bool = Field(description="Whether to enable detailed TLS diagnostic logging.")
    tls_opt_export_cert_data: bool = Field(
        description="Whether to export client certificate data to environment variables.",
    )
    tls_opt_no_empty_fragments: bool = Field(
        description=(
            "Whether to disable empty TLS record fragments to improve compatibility with some clients. Disabling "
            "increases vulnerability to some attack vectors."
        ),
    )
    tls_opt_no_session_reuse_required: bool = Field(
        description="Whether to disable the requirement for TLS session reuse.",
    )
    tls_opt_stdenvvars: bool = Field(
        description="Whether to export standard TLS environment variables for use by external programs.",
    )
    tls_opt_dns_name_required: bool = Field(
        description=(
            "Whether to require client certificates to contain a DNS name in the Subject Alternative Name extension. "
            "The `reversedns` setting must also be enabled."
        ),
    )
    tls_opt_ip_address_required: bool = Field(
        description=(
            "Whether to require client certificates to contain an IP address in the Subject Alternative Name extension."
        ),
    )
    ssltls_certificate: int | None = Field(
        description=(
            "ID of the certificate to use for TLS/SSL connections. `null` to use the default system certificate."
        ),
    )
    options: str = Field(
        description=(
            "Additional ProFTPD configuration directives to include in the server configuration. Manual directives may "
            "render the FTP service non-functional and should be used with caution."
        ),
    )

    @field_validator("passiveportsmin", "passiveportsmax")
    @classmethod
    def validate_passiveport(cls, field_value: int, values: ValidationInfo):
        minport = 1024
        maxport = 65535

        if not (field_value == 0 or (minport <= field_value <= maxport)):
            raise ValueError(f"Must be 0 (to reset) else between {minport} and {maxport}")

        return field_value


@single_argument_args('ftp_update')
class FTPUpdateArgs(FTPEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class FTPUpdateResult(BaseModel):
    result: FTPEntry
