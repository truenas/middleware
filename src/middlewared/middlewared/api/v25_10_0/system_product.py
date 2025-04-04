from typing import Literal

from middlewared.api.base import BaseModel, NonEmptyString


__all__ = (
    "SystemProductFeatureEnabledArgs",
    "SystemProductFeatureEnabledResult",
    "SystemProductLicenseArgs",
    "SystemProductLicenseResult",
    "SystemProductReleaseNotesUrlArgs",
    "SystemProductReleaseNotesUrlResult",
    "SystemProductTypeArgs",
    "SystemProductTypeResult",
    "SystemProductVersionArgs",
    "SystemProductVersionResult",
    "SystemProductVersionShortArgs",
    "SystemProductVersionShortResult",
)


class SystemProductFeatureEnabledArgs(BaseModel):
    feature: Literal["DEDUP", "FIBRECHANNEL", "VM"]


class SystemProductFeatureEnabledResult(BaseModel):
    result: bool


class SystemProductLicenseArgs(BaseModel):
    license: NonEmptyString


class SystemProductLicenseResult(BaseModel):
    result: None


class SystemProductReleaseNotesUrlArgs(BaseModel):
    version_str: NonEmptyString | None = None


class SystemProductReleaseNotesUrlResult(BaseModel):
    result: str


class SystemProductTypeArgs(BaseModel):
    pass


class SystemProductTypeResult(BaseModel):
    result: Literal["COMMUNITY_EDITION", "ENTERPRISE"]


class SystemProductVersionArgs(BaseModel):
    pass


class SystemProductVersionResult(BaseModel):
    result: str


class SystemProductVersionShortArgs(BaseModel):
    pass


class SystemProductVersionShortResult(BaseModel):
    result: str
