from typing import Literal

from pydantic.types import StringConstraints
from pydantic import EmailStr, Field, Secret
from typing_extensions import Annotated, Union

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args
)

__all__ = ["SnmpEntry",
           "SnmpUpdateArgs", "SnmpUpdateResult"]


class SnmpEntry(BaseModel):
    location: str
    contact: Union[EmailStr, Annotated[str, StringConstraints(pattern=r'^[-_a-zA-Z0-9\s]*$')]]
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
class SnmpUpdateArgs(SnmpEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SnmpUpdateResult(BaseModel):
    result: SnmpEntry
