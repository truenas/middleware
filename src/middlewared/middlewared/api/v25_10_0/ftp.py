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

__all__ = ["FtpEntry",
           "FTPUpdateArgs", "FTPUpdateResult"]

TLS_PolicyOptions = Literal[
    "", "on", "off", "data", "!data", "auth", "ctrl", "ctrl+data", "ctrl+!data", "auth+data", "auth+!data"
]


class FtpEntry(BaseModel):
    id: int
    """Placeholder identifier.  Not used as there is only one."""
    port: Annotated[int, Field(ge=1, le=65535)]
    """TCP port number on which the FTP service listens for incoming connections."""
    clients: Annotated[int, Field(ge=1, le=10000)]
    """Maximum number of simultaneous client connections allowed."""
    ipconnections: Annotated[int, Field(ge=0, le=1000)]
    """Maximum number of connections allowed from a single IP address. 0 means unlimited."""
    loginattempt: Annotated[int, Field(ge=0, le=1000)]
    """Maximum number of failed login attempts before blocking an IP address. 0 disables this limit."""
    timeout: Annotated[int, Field(ge=0, le=10000)]
    """Idle timeout in seconds before disconnecting inactive clients. 0 disables timeout."""
    timeout_notransfer: Annotated[int, Field(ge=0, le=10000)]
    """Timeout in seconds for clients that connect but do not transfer data. 0 disables timeout."""
    onlyanonymous: bool
    """Whether to allow only anonymous FTP access, disabling authenticated user login."""
    anonpath: str | None
    """Filesystem path for anonymous FTP users. `null` to use the default anonymous FTP directory."""
    onlylocal: bool
    """Whether to allow only local system users to login, disabling anonymous access."""
    banner: str
    """Welcome message displayed to FTP clients upon connection."""
    filemask: UnixPerm
    """Default Unix permissions (umask) for files created by FTP users."""
    dirmask: UnixPerm
    """Default Unix permissions (umask) for directories created by FTP users."""
    fxp: bool
    """Whether to enable File eXchange Protocol (FXP) for server-to-server transfers."""
    resume: bool
    """Whether to allow clients to resume interrupted file transfers."""
    defaultroot: bool
    """Whether to restrict users to their home directories (chroot jail)."""
    ident: bool
    """Whether to perform RFC 1413 ident lookups on connecting clients."""
    reversedns: bool
    """Whether to perform reverse DNS lookups on client IP addresses for logging."""
    masqaddress: str
    """Public IP address to advertise to clients for passive mode connections when behind NAT."""
    passiveportsmin: int
    """Minimum port number for passive mode data connections. Must be 0 or between 1024-65535."""
    passiveportsmax: int
    """Maximum port number for passive mode data connections. Must be 0 or between 1024-65535."""
    localuserbw: Annotated[int, Field(ge=0)]
    """Maximum upload bandwidth in KiB/s for local users. 0 means unlimited."""
    localuserdlbw: Annotated[int, Field(ge=0)]
    """Maximum download bandwidth in bytes per second for local users. 0 means unlimited."""
    anonuserbw: Annotated[int, Field(ge=0)]
    """Maximum upload bandwidth in bytes per second for anonymous users. 0 means unlimited."""
    anonuserdlbw: Annotated[int, Field(ge=0)]
    """Maximum download bandwidth in bytes per second for anonymous users. 0 means unlimited."""
    tls: bool
    """Whether to enable TLS/SSL encryption for FTP connections."""
    tls_policy: TLS_PolicyOptions
    """TLS policy for connections. Values include: `"on"` (required), `"off"` (disabled), `"data"` (data only), \
    `"auth"` (authentication only), `"ctrl"` (control only), or combinations with `+` and `!` modifiers."""
    tls_opt_allow_client_renegotiations: bool
    """Whether to allow TLS clients to initiate renegotiation of the TLS connection."""
    tls_opt_allow_dot_login: bool
    """Whether to allow .ftpaccess files to override TLS requirements for specific users."""
    tls_opt_allow_per_user: bool
    """Whether to allow per-user TLS configuration overrides."""
    tls_opt_common_name_required: bool
    """Whether to require client certificates to have a Common Name field."""
    tls_opt_enable_diags: bool
    """Whether to enable detailed TLS diagnostic logging."""
    tls_opt_export_cert_data: bool
    """Whether to export client certificate data to environment variables."""
    tls_opt_no_empty_fragments: bool
    """Whether to disable empty TLS record fragments to improve compatibility with some clients."""
    tls_opt_no_session_reuse_required: bool
    """Whether to disable the requirement for TLS session reuse."""
    tls_opt_stdenvvars: bool
    """Whether to export standard TLS environment variables for use by external programs."""
    tls_opt_dns_name_required: bool
    """Whether to require client certificates to contain a DNS name in the Subject Alternative Name extension."""
    tls_opt_ip_address_required: bool
    """Whether to require client certificates to contain an IP address in the Subject Alternative Name extension."""
    ssltls_certificate: int | None
    """ID of the certificate to use for TLS/SSL connections. `null` to use the default system certificate."""
    options: str
    """Additional ProFTPD configuration directives to include in the server configuration."""

    @field_validator("passiveportsmin", "passiveportsmax")
    @classmethod
    def validate_passiveport(cls, field_value: int, values: ValidationInfo):
        minport = 1024
        maxport = 65535

        if not (field_value == 0 or (minport <= field_value <= maxport)):
            raise ValueError(f"Must be 0 (to reset) else between {minport} and {maxport}")

        return field_value


@single_argument_args('ftp_update')
class FTPUpdateArgs(FtpEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class FTPUpdateResult(BaseModel):
    result: FtpEntry
