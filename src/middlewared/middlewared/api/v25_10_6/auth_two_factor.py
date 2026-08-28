from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass


__all__ = [
    'TwoFactorAuthEntry', 'TwoFactorAuthUpdateArgs', 'TwoFactorAuthUpdateResult'
]


class TwoFactorAuthServices(BaseModel):
    ssh: bool = Field(default=False, description="Whether two-factor authentication is required for SSH connections.")


class TwoFactorAuthEntry(BaseModel):
    enabled: bool = Field(description="Whether two-factor authentication is enabled system-wide.")
    services: TwoFactorAuthServices = Field(
        description="Configuration for which services require two-factor authentication.",
    )
    window: int = Field(ge=0, description="Time window in seconds for TOTP token validation (minimum 0).")
    id: int = Field(description="Unique identifier for the two-factor authentication configuration.")


class TwoFactorAuthUpdate(TwoFactorAuthEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class TwoFactorAuthUpdateArgs(BaseModel):
    auth_twofactor_update: TwoFactorAuthUpdate = Field(
        description="Updated two-factor authentication configuration settings.",
    )


class TwoFactorAuthUpdateResult(BaseModel):
    result: TwoFactorAuthEntry = Field(description="The updated two-factor authentication configuration.")
