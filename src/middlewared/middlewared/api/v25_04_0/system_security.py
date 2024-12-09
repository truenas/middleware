from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    single_argument_args
)

__all__ = ['SystemSecurityEntry', 'SystemSecurityUpdateArgs', 'SystemSecurityUpdateResult']


class SystemSecurityEntry(BaseModel):
    id: int
    stig_enabled: bool


@single_argument_args('system_security_update')
class SystemSecurityUpdateArgs(SystemSecuityEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SystemSecurityUpdateResult(BaseModel:
    result: SystemSecurityEntry
