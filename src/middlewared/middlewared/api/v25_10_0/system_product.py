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
    "SystemExperimentalArgs",
    "SystemExperimentalResult",
)


class SystemFeatureEnabledArgs(BaseModel):
    feature: Literal["DEDUP", "FIBRECHANNEL", "VM"]


class SystemFeatureEnabledResult(BaseModel):
    result: bool


class SystemLicenseUpdateArgs(BaseModel):
    license: NonEmptyString


class SystemLicenseUpdateResult(BaseModel):
    result: None


class SystemReleaseNotesUrlArgs(BaseModel):
    version_str: NonEmptyString | None = None


class SystemReleaseNotesUrlResult(BaseModel):
    result: str


class SystemProductTypeArgs(BaseModel):
    pass


class SystemProductTypeResult(BaseModel):
    result: Literal["COMMUNITY_EDITION", "ENTERPRISE"]


class SystemVersionArgs(BaseModel):
    pass


class SystemVersionResult(BaseModel):
    result: str


class SystemVersionShortArgs(BaseModel):
    pass


class SystemVersionShortResult(BaseModel):
    result: str


class SystemExperimentalArgs(BaseModel):
    pass


class SystemExperimentalResult(BaseModel):
    result: bool
