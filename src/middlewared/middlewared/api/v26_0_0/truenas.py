from typing import Any

from pydantic import Field

from middlewared.api.base import BaseModel, LongString, LongNonEmptyString

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
    'TrueNASLicenseInfoArgs', 'TrueNASLicenseInfoResult',
    'TrueNASLicenseFingerprintArgs', 'TrueNASLicenseFingerprintResult',
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
    license: LongNonEmptyString = Field(description="PEM-wrapped license to apply to the system.")
    options: TrueNASLicenseUploadOptions = Field(default=TrueNASLicenseUploadOptions(), description="Options.")


class TrueNASLicenseUploadResult(BaseModel):
    result: None = Field(description="Returns `null` on successful license upload.")


class TrueNASLicenseInfoArgs(BaseModel):
    pass


class TrueNASLicenseInfoResult(BaseModel):
    result: dict[str, Any] | None = Field(
        description="Parsed license JSON object, or `null` if no license file exists.",
    )


class TrueNASLicenseFingerprintArgs(BaseModel):
    pass


class TrueNASLicenseFingerprintResult(BaseModel):
    result: LongString = Field(description="Base64-encoded JSON of the system hardware fingerprint.")
