from typing import Annotated, Literal

from pydantic.types import StringConstraints
from pydantic import EmailStr, Field, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args
)

__all__ = ["SnmpEntry",
           "SNMPUpdateArgs", "SNMPUpdateResult"]


class SnmpEntry(BaseModel):
    location: str
    contact: EmailStr | Annotated[str, StringConstraints(pattern=r'^[-_a-zA-Z0-9\s]*$')]
    traps: bool
    v3: bool
    community: str = Field(pattern=r'^[-_a-zA-Z0-9\s]*$', default='public')
    v3_username: str = Field(max_length=20)
    v3_authtype: Literal['', 'MD5', 'SHA']
    v3_password: Secret[str]
    v3_privproto: Literal[None, 'AES', 'DES'] | None
    v3_privpassphrase: Secret[str | None] = None
    loglevel: int = Field(ge=0, le=7)
    options: str
    zilstat: bool
    id: int


@single_argument_args('snmp_update')
class SNMPUpdateArgs(SnmpEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SNMPUpdateResult(BaseModel):
    result: SnmpEntry
