from datetime import date
from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, LongString, LongNonEmptyString, NonEmptyString

from .support import SupportNewTicket


__all__ = [
    'TrueNASSetProductionArgs', 'TrueNASSetProductionResult',
    'TrueNASIsProductionArgs', 'TrueNASIsProductionResult',
    'TrueNASAcceptEulaArgs', 'TrueNASAcceptEulaResult',
    'TrueNASIsEulaAcceptedArgs', 'TrueNASIsEulaAcceptedResult',
    'TrueNASGetEulaArgs', 'TrueNASGetEulaResult',
    'TrueNASIsIxHardwareArgs', 'TrueNASIsIxHardwareResult',
    'TrueNASGetChassisHardwareArgs', 'TrueNASGetChassisHardwareResult',
    'TrueNASManagedByTruecommandArgs', 'TrueNASManagedByTruecommandResult',
    'TrueNASLicenseUploadOptions', 'TrueNASLicenseUploadArgs', 'TrueNASLicenseUploadResult',
    'LicenseFeatureEntry', 'LicenseInfoEntry',
    'TrueNASLicenseInfoArgs', 'TrueNASLicenseInfoResult',
    'TrueNASLicenseFingerprintArgs', 'TrueNASLicenseFingerprintResult',
    'EntitlementEntry', 'EntitlementsInfo',
    'TrueNASEntitlementsInfoArgs', 'TrueNASEntitlementsInfoResult',
    'TrueNASEntitlementsCheckArgs', 'TrueNASEntitlementsCheckResult',
]


class TrueNASManagedByTruecommandArgs(BaseModel):
    pass


class TrueNASManagedByTruecommandResult(BaseModel):
    result: bool = Field(description="Whether this TrueNAS system is currently managed by TrueCommand.")


class TrueNASGetChassisHardwareArgs(BaseModel):
    pass


class TrueNASGetChassisHardwareResult(BaseModel):
    result: str = Field(description="Hardware chassis model identifier for this TrueNAS system.")


class TrueNASIsIxHardwareArgs(BaseModel):
    pass


class TrueNASIsIxHardwareResult(BaseModel):
    result: bool = Field(description="Whether this system is running on iXsystems hardware.")


class TrueNASGetEulaArgs(BaseModel):
    pass


class TrueNASGetEulaResult(BaseModel):
    result: LongString | None = Field(
        description="Full text of the End User License Agreement. `null` if no EULA is required.",
    )


class TrueNASIsEulaAcceptedArgs(BaseModel):
    pass


class TrueNASIsEulaAcceptedResult(BaseModel):
    result: bool = Field(description="Whether the End User License Agreement has been formally accepted.")


class TrueNASAcceptEulaArgs(BaseModel):
    pass


class TrueNASAcceptEulaResult(BaseModel):
    result: None = Field(description="Returns `null` on successful EULA acceptance.")


class TrueNASIsProductionArgs(BaseModel):
    pass


class TrueNASIsProductionResult(BaseModel):
    result: bool = Field(description="Whether this TrueNAS system is configured for production use.")


class TrueNASSetProductionArgs(BaseModel):
    production: bool = Field(description="Whether to configure the system for production use.")
    attach_debug: bool = Field(
        default=False,
        description="Whether to attach debug information when transitioning to production mode.",
    )


class TrueNASSetProductionResult(BaseModel):
    result: SupportNewTicket | None = Field(
        description="Support ticket details if system was newly marked as production. `null` otherwise.",
    )


class TrueNASLicenseUploadOptions(BaseModel):
    ha_propagate: bool = Field(default=True, description="Propagate to another HA system.")


class TrueNASLicenseUploadArgs(BaseModel):
    license: Secret[LongNonEmptyString] = Field(description="PEM-wrapped license to apply to the system.")
    options: TrueNASLicenseUploadOptions = Field(default=TrueNASLicenseUploadOptions(), description="Options.")


class TrueNASLicenseUploadResult(BaseModel):
    result: None = Field(description="Returns `null` on successful license upload.")


class LicenseFeatureEntry(BaseModel):
    """A single feature an installed license grants."""

    name: str = Field(description="Feature identifier, for example `SUPPORT` or `VMS`.")
    start_date: date | None = Field(
        description="Date the feature became active, or `null` when the license records no start date.",
    )
    expires_at: date | None = Field(description="Date the feature expires, or `null` when it is perpetual.")
    source: str = Field(description="How the feature was granted, for example `enterprise`.")
    type: str | None = Field(
        description="Tier qualifier the feature carries, for example `GOLD`. `null` when it carries none.",
    )


class LicenseInfoEntry(BaseModel):
    """An installed license, normalized identically whichever format produced it."""

    id: str = Field(description="Identifier of the installed license.")
    type: str = Field(
        description=(
            "License type: one of `ENTERPRISE_SINGLE`, `ENTERPRISE_HA`, `COMMERCIAL`, `COMMUNITY` or `UNKNOWN`. "
            "New values may be added; treat an unrecognized value as `UNKNOWN`."
        ),
    )
    model: str | None = Field(description="Hardware model the license was issued for, or `null` if unspecified.")
    features: list[LicenseFeatureEntry] = Field(description="Every feature this license grants.")
    serials: list[str] = Field(description="System serial numbers the license covers.")
    enclosures: dict[str, int] = Field(description="Count of licensed expansion shelves, keyed by enclosure model.")
    contract_type: str | None = Field(
        description="Support contract tier, or `null` when the license carries no support entitlement.",
    )


class TrueNASLicenseInfoArgs(BaseModel):
    pass


class TrueNASLicenseInfoResult(BaseModel):
    result: LicenseInfoEntry | None = Field(
        description="Parsed license, or `null` if no license is installed.",
    )


class TrueNASLicenseFingerprintArgs(BaseModel):
    pass


class TrueNASLicenseFingerprintResult(BaseModel):
    result: LongString = Field(description="Base64-encoded JSON of the system hardware fingerprint.")


class EntitlementEntry(BaseModel):
    """Decision for a single license-gated feature."""

    entitled: bool = Field(description="Whether this system is entitled to use the feature.")
    reason: Literal[
        "ENTITLED", "NO_LICENSE", "KEY_MISSING", "WRONG_HARDWARE", "TIER_INSUFFICIENT", "WRONG_LICENSE_TYPE",
        "NOT_GATED",
    ] = Field(
        description=(
            "Machine-readable classification of the decision:\n"
            "\n"
            "* `ENTITLED`: the feature is available\n"
            "* `NO_LICENSE`: no license is installed and the feature requires one\n"
            "* `KEY_MISSING`: a license is installed but does not carry this feature\n"
            "* `WRONG_HARDWARE`: this hardware can never provide the feature\n"
            "* `TIER_INSUFFICIENT`: the support tier does not cover the feature\n"
            "* `WRONG_LICENSE_TYPE`: the license type does not cover the feature\n"
            "* `NOT_GATED`: nothing on this system restricts the feature\n"
            "\n"
            "New values may be added; treat an unrecognized value as a generic denial."
        )
    )
    message: str = Field(description="Human-readable explanation of the decision. Empty when entitled.")


class EntitlementsInfo(BaseModel):
    features: dict[NonEmptyString, EntitlementEntry] = Field(
        description=(
            "Entitlement decision for every license-gated feature known to this system, keyed by feature "
            "identifier. Identifiers are added over time: ignore keys you do not recognize, and treat an "
            "absent key as not gated."
        )
    )


class TrueNASEntitlementsInfoArgs(BaseModel):
    pass


class TrueNASEntitlementsInfoResult(BaseModel):
    result: EntitlementsInfo = Field(description="Entitlement decisions for all license-gated features on this system.")


class TrueNASEntitlementsCheckArgs(BaseModel):
    feature: NonEmptyString = Field(
        description=(
            "Feature identifier to evaluate. A feature this system does not gate is reported as "
            "`NOT_GATED`, the same as its absence from the `truenas.entitlements.info` map."
        )
    )


class TrueNASEntitlementsCheckResult(BaseModel):
    result: EntitlementEntry = Field(description="Entitlement decision for the requested feature.")
