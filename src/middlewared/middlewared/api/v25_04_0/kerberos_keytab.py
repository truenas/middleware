from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
)
from pydantic import Secret
from typing import Literal


__all__ = [
    'KerberosKeytabEntry',
    'KerberosKeytabCreateArgs', 'KerberosKeytabCreateResult',
    'KerberosKeytabUpdateArgs', 'KerberosKeytabUpdateResult',
    'KerberosKeytabDeleteArgs', 'KerberosKeytabDeleteResult',
]


class KerberosKeytabEntry(BaseModel):
    id: int
    file: Secret[NonEmptyString]
    name: NonEmptyString


class KerberosKeytabCreate(KerberosKeytabEntry):
    id: Excluded = excluded_field()


class KerberosKeytabUpdate(KerberosKeytabCreate, metaclass=ForUpdateMetaclass):
    pass


class KerberosKeytabCreateArgs(BaseModel):
    kerberos_keytab_create: KerberosKeytabCreate


class KerberosKeytabUpdateArgs(BaseModel):
    id: int
    kerberos_keytab_update: KerberosKeytabUpdate


class KerberosKeytabCreateResult(BaseModel):
    result: KerberosKeytabEntry


class KerberosKeytabUpdateResult(BaseModel):
    result: KerberosKeytabEntry


class KerberosKeytabDeleteArgs(BaseModel):
    id: int


class KerberosKeytabDeleteResult(BaseModel):
    result: Literal[True]
