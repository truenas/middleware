from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, LongString, TcpPort, excluded_field

__all__ = ['SSHEntry', 'SSHBindifaceChoicesArgs', 'SSHBindifaceChoicesResult', 'SSHUpdateArgs', 'SSHUpdateResult',]


class SSHEntry(BaseModel):
    id: int = Field(description="Unique identifier for the SSH service configuration.")
    bindiface: list[str] = Field(description="Array of network interface names to bind the SSH service to.")
    tcpport: TcpPort = Field(description="TCP port number for SSH connections.")
    password_login_groups: list[str] = Field(description="Array of group names allowed to authenticate with passwords.")
    passwordauth: bool = Field(description="Whether password authentication is enabled.")
    kerberosauth: bool = Field(description="Whether Kerberos authentication is enabled.")
    tcpfwd: bool = Field(description="Whether TCP forwarding is enabled.")
    compression: bool = Field(description="Whether compression is enabled for SSH connections.")
    sftp_log_level: Literal['', 'QUIET', 'FATAL', 'ERROR', 'INFO', 'VERBOSE', 'DEBUG', 'DEBUG2', 'DEBUG3'] = Field(
        description="Logging level for SFTP subsystem (empty string means default).",
    )
    sftp_log_facility: Literal[
        '', 'DAEMON', 'USER', 'AUTH', 'LOCAL0', 'LOCAL1', 'LOCAL2', 'LOCAL3', 'LOCAL4', 'LOCAL5', 'LOCAL6', 'LOCAL7'
    ] = Field(description="Syslog facility for SFTP logging (empty string means default).")
    weak_ciphers: list[Literal['AES128-CBC', 'NONE']] = Field(
        description="Array of weak ciphers to enable for compatibility with legacy clients.",
    )
    options: LongString = Field(description="Additional SSH daemon configuration options.")
    privatekey: LongString = Field(description="SSH host private key data.")
    host_dsa_key: LongString | None = Field(description="DSA host private key. `null` if not configured.")
    host_dsa_key_pub: LongString | None = Field(description="DSA host public key. `null` if not configured.")
    host_dsa_key_cert_pub: LongString | None = Field(
        description="DSA host certificate public key. `null` if not configured.",
    )
    host_ecdsa_key: LongString | None = Field(description="ECDSA host private key. `null` if not configured.")
    host_ecdsa_key_pub: LongString | None = Field(description="ECDSA host public key. `null` if not configured.")
    host_ecdsa_key_cert_pub: LongString | None = Field(
        description="ECDSA host certificate public key. `null` if not configured.",
    )
    host_ed25519_key: LongString | None = Field(description="Ed25519 host private key. `null` if not configured.")
    host_ed25519_key_pub: LongString | None = Field(description="Ed25519 host public key. `null` if not configured.")
    host_ed25519_key_cert_pub: LongString | None = Field(
        description="Ed25519 host certificate public key. `null` if not configured.",
    )
    host_key: LongString | None = Field(description="Legacy SSH host private key. `null` if not configured.")
    host_key_pub: LongString | None = Field(description="Legacy SSH host public key. `null` if not configured.")
    host_rsa_key: LongString | None = Field(description="RSA host private key. `null` if not configured.")
    host_rsa_key_pub: LongString | None = Field(description="RSA host public key. `null` if not configured.")
    host_rsa_key_cert_pub: LongString | None = Field(
        description="RSA host certificate public key. `null` if not configured.",
    )


class SSHUpdate(SSHEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    privatekey: Excluded = excluded_field()
    host_dsa_key: Excluded = excluded_field()
    host_dsa_key_pub: Excluded = excluded_field()
    host_dsa_key_cert_pub: Excluded = excluded_field()
    host_ecdsa_key: Excluded = excluded_field()
    host_ecdsa_key_pub: Excluded = excluded_field()
    host_ecdsa_key_cert_pub: Excluded = excluded_field()
    host_ed25519_key: Excluded = excluded_field()
    host_ed25519_key_pub: Excluded = excluded_field()
    host_ed25519_key_cert_pub: Excluded = excluded_field()
    host_key: Excluded = excluded_field()
    host_key_pub: Excluded = excluded_field()
    host_rsa_key: Excluded = excluded_field()
    host_rsa_key_pub: Excluded = excluded_field()
    host_rsa_key_cert_pub: Excluded = excluded_field()


class SSHBindifaceChoicesArgs(BaseModel):
    pass


class SSHBindifaceChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Result of `interface.choices`.")


class SSHUpdateArgs(BaseModel):
    data: SSHUpdate = Field(description="Updated SSH service configuration.")


class SSHUpdateResult(BaseModel):
    result: SSHEntry = Field(description="The updated SSH service configuration.")
