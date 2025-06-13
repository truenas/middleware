from typing import Literal

from middlewared.api.base import BaseModel, LongString, Excluded, excluded_field, ForUpdateMetaclass, TcpPort


__all__ = ['SSHEntry', 'SSHBindifaceChoicesArgs', 'SSHBindifaceChoicesResult', 'SSHUpdateArgs', 'SSHUpdateResult',]


class SSHEntry(BaseModel):
    id: int
    bindiface: list[str]
    tcpport: TcpPort
    password_login_groups: list[str]
    passwordauth: bool
    kerberosauth: bool
    tcpfwd: bool
    compression: bool
    sftp_log_level: Literal['', 'QUIET', 'FATAL', 'ERROR', 'INFO', 'VERBOSE', 'DEBUG', 'DEBUG2', 'DEBUG3']
    sftp_log_facility: Literal[
        '', 'DAEMON', 'USER', 'AUTH', 'LOCAL0', 'LOCAL1', 'LOCAL2', 'LOCAL3', 'LOCAL4', 'LOCAL5', 'LOCAL6', 'LOCAL7'
    ]
    weak_ciphers: list[Literal['AES128-CBC', 'NONE']]
    options: LongString
    privatekey: LongString
    host_dsa_key: LongString | None
    host_dsa_key_pub: LongString | None
    host_dsa_key_cert_pub: LongString | None
    host_ecdsa_key: LongString | None
    host_ecdsa_key_pub: LongString | None
    host_ecdsa_key_cert_pub: LongString | None
    host_ed25519_key: LongString | None
    host_ed25519_key_pub: LongString | None
    host_ed25519_key_cert_pub: LongString | None
    host_key: LongString | None
    host_key_pub: LongString | None
    host_rsa_key: LongString | None
    host_rsa_key_pub: LongString | None
    host_rsa_key_cert_pub: LongString | None


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
    result: dict[str, str]
    """Result of `interface.choices`."""


class SSHUpdateArgs(BaseModel):
    data: SSHUpdate


class SSHUpdateResult(BaseModel):
    result: SSHEntry
