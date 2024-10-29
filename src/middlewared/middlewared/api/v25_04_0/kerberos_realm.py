from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
)
from typing import Literal


__all__ = [
    'KerberosRealmEntry',
    'KerberosRealmCreateArgs', 'KerberosRealmCreateResult',
    'KerberosRealmUpdateArgs', 'KerberosRealmUpdateResult',
    'KerberosRealmDeleteArgs', 'KerberosRealmDeleteResult',
]


class KerberosRealmEntry(BaseModel):
    id: int
    realm: NonEmptyString
    kdc: list[str]
    admin_server: list[str]
    kpasswd_server: list[str]


class KerberosRealmCreate(KerberosRealmEntry):
    id: Excluded = excluded_field()


class KerberosRealmUpdate(KerberosRealmCreate, metaclass=ForUpdateMetaclass):
    pass


class KerberosRealmCreateArgs(BaseModel):
    kerberos_realm_create: KerberosRealmCreate


class KerberosRealmUpdateArgs(BaseModel):
    id: int
    kerberos_realm_update: KerberosRealmUpdate


class KerberosRealmCreateResult(BaseModel):
    result: KerberosRealmEntry


class KerberosRealmUpdateResult(BaseModel):
    result: KerberosRealmEntry


class KerberosRealmDeleteArgs(BaseModel):
    id: int


class KerberosRealmDeleteResult(BaseModel):
    result: Literal[True]
