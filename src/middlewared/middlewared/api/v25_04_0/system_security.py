from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    single_argument_args
)

__all__ = [
    'SystemSecurityEntry', 'SystemSecurityUpdateArgs', 'SystemSecurityUpdateResult',
    'SystemSecurityFipsAvailableArgs', 'SystemSecurityFipsAvailableResult',
    'SystemSecurityFipsEnabledArgs', 'SystemSecurityFipsEnabledResult',
]


class SystemSecurityEntry(BaseModel):
    id: int
    enable_fips: bool
    """ When set, enables FIPS mode. """
    enable_gpos_stig: bool
    """ When set, enables compatibility with the General Purpose Operating System STIG. """


@single_argument_args('system_security_update')
class SystemSecurityUpdateArgs(SystemSecurityEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SystemSecurityUpdateResult(BaseModel):
    result: SystemSecurityEntry


class SystemSecurityFipsAvailableArgs(BaseModel):
    pass


class SystemSecurityFipsAvailableResult(BaseModel):
    result: bool


class SystemSecurityFipsEnabledArgs(BaseModel):
    pass


class SystemSecurityFipsEnabledResult(BaseModel):
    result: bool
