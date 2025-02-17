from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass


__all__ = [
    'TwoFactorAuthEntry', 'TwoFactorAuthUpdateArgs', 'TwoFactorAuthUpdateResult'
]


class TwoFactorAuthServices(BaseModel):
    ssh: bool = False


class TwoFactorAuthEntry(BaseModel):
    enabled: bool
    services: TwoFactorAuthServices
    window: int = Field(ge=0)
    id: int


class TwoFactorAuthUpdate(TwoFactorAuthEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class TwoFactorAuthUpdateArgs(BaseModel):
    auth_twofactor_update: TwoFactorAuthUpdate


class TwoFactorAuthUpdateResult(BaseModel):
    result: TwoFactorAuthEntry
