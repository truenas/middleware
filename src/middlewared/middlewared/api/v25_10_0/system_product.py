from typing import Literal

from middlewared.api.base import BaseModel, NonEmptyString


__all__ = (
    "SystemFeatureEnabledArgs",
    "SystemFeatureEnabledResult",
    "SystemLicenseUpdateArgs",
    "SystemLicenseUpdateResult",
    "SystemReleaseNotesUrlArgs",
    "SystemReleaseNotesUrlResult",
    "SystemProductTypeArgs",
    "SystemProductTypeResult",
    "SystemVersionArgs",
    "SystemVersionResult",
    "SystemVersionShortArgs",
    "SystemVersionShortResult",
)


class SystemFeatureEnabledArgs(BaseModel):
    feature: Literal["DEDUP", "FIBRECHANNEL", "VM"]
    """Feature to check for availability on this system."""


class SystemFeatureEnabledResult(BaseModel):
    result: bool
    """Whether the specified feature is enabled on this system."""


class SystemLicenseUpdateArgs(BaseModel):
    license: NonEmptyString
    """License key to apply to the system."""


class SystemLicenseUpdateResult(BaseModel):
    result: None
    """Returns `null` on successful license update."""


class SystemReleaseNotesUrlArgs(BaseModel):
    version_str: NonEmptyString | None = None
    """Version string to get release notes for. `null` for current version."""


class SystemReleaseNotesUrlResult(BaseModel):
    result: str
    """URL to the release notes for the specified version."""


class SystemProductTypeArgs(BaseModel):
    pass


class SystemProductTypeResult(BaseModel):
    result: Literal["COMMUNITY_EDITION", "ENTERPRISE"]
    """Product type of this TrueNAS system."""


class SystemVersionArgs(BaseModel):
    pass


class SystemVersionResult(BaseModel):
    result: str
    """Full version string of the TrueNAS system."""


class SystemVersionShortArgs(BaseModel):
    pass


class SystemVersionShortResult(BaseModel):
    result: str
    """Short version string of the TrueNAS system."""
