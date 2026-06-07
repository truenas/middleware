from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = ["SystemRebootInfoArgs", "RebootInfo", "SystemRebootInfoResult", "SystemRebootInfoChangedEvent"]


class SystemRebootInfoArgs(BaseModel):
    pass


class RebootRequiredReason(BaseModel):
    code: str = Field(description="Code identifying the reason for required reboot.")
    reason: str = Field(description="Human-readable description of why a reboot is required.")


class RebootInfo(BaseModel):
    boot_id: str = Field(description="Unique identifier for the current boot session.")
    reboot_required_reasons: list[RebootRequiredReason] = Field(
        description="Array of reasons why a system reboot is required.",
    )


class SystemRebootInfoResult(BaseModel):
    result: RebootInfo = Field(description="Information about the current boot session and reboot requirements.")


class SystemRebootInfoChangedEvent(BaseModel):
    id: None = Field(description="Always `null`.")
    fields: RebootInfo = Field(description="Event fields.")
