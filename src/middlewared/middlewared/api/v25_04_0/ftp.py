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
    id: int
    port: Annotated[int, Field(ge=1, le=65535)]
    clients: Annotated[int, Field(ge=1, le=10000)]
    ipconnections: Annotated[int, Field(ge=0, le=1000)]
    loginattempt: Annotated[int, Field(ge=0, le=1000)]
    timeout: Annotated[int, Field(ge=0, le=10000)]
    timeout_notransfer: Annotated[int, Field(ge=0, le=10000)]
    onlyanonymous: bool
    anonpath: str | None
    onlylocal: bool
    banner: str
    filemask: UnixPerm
    dirmask: UnixPerm
    fxp: bool
    resume: bool
    defaultroot: bool
    ident: bool
    reversedns: bool
    masqaddress: str
    passiveportsmin: int
    passiveportsmax: int
    localuserbw: Annotated[int, Field(ge=0)]
    localuserdlbw: Annotated[int, Field(ge=0)]
    anonuserbw: Annotated[int, Field(ge=0)]
    anonuserdlbw: Annotated[int, Field(ge=0)]
    tls: bool
    tls_policy: TLS_PolicyOptions
    tls_opt_allow_client_renegotiations: bool
    tls_opt_allow_dot_login: bool
    tls_opt_allow_per_user: bool
    tls_opt_common_name_required: bool
    tls_opt_enable_diags: bool
    tls_opt_export_cert_data: bool
    tls_opt_no_empty_fragments: bool
    tls_opt_no_session_reuse_required: bool
    tls_opt_stdenvvars: bool
    tls_opt_dns_name_required: bool
    tls_opt_ip_address_required: bool
    ssltls_certificate: int | None
    options: str

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
