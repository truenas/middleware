from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass


__all__ = [
    'TwoFactorAuthEntry', 'TwoFactorAuthUpdateArgs', 'TwoFactorAuthUpdateResult'
]


class TwoFactorAuthServices(BaseModel):
    ssh: bool = False
    """Whether two-factor authentication is required for SSH connections."""


class TwoFactorAuthEntry(BaseModel):
    enabled: bool
    """Whether two-factor authentication is enabled system-wide."""
    services: TwoFactorAuthServices
    """Configuration for which services require two-factor authentication."""
    window: int = Field(ge=0)
    """Time window in seconds for TOTP token validation (minimum 0)."""
    id: int
    """Unique identifier for the two-factor authentication configuration."""


class TwoFactorAuthUpdate(TwoFactorAuthEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class TwoFactorAuthUpdateArgs(BaseModel):
    auth_twofactor_update: TwoFactorAuthUpdate
    """Updated two-factor authentication configuration settings."""


class TwoFactorAuthUpdateResult(BaseModel):
    result: TwoFactorAuthEntry
    """The updated two-factor authentication configuration."""
