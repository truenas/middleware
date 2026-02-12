from middlewared.api.base import BaseModel

__all__ = ["SystemRebootInfoArgs", "RebootInfo", "SystemRebootInfoResult", "SystemRebootInfoChangedEvent"]


class SystemRebootInfoArgs(BaseModel):
    pass


class RebootRequiredReason(BaseModel):
    code: str
    """Code identifying the reason for required reboot."""
    reason: str
    """Human-readable description of why a reboot is required."""


class RebootInfo(BaseModel):
    boot_id: str
    """Unique identifier for the current boot session."""
    reboot_required_reasons: list[RebootRequiredReason]
    """Array of reasons why a system reboot is required."""


class SystemRebootInfoResult(BaseModel):
    result: RebootInfo
    """Information about the current boot session and reboot requirements."""


class SystemRebootInfoChangedEvent(BaseModel):
    id: None
    """Always `null`."""
    fields: RebootInfo
    """Event fields."""
