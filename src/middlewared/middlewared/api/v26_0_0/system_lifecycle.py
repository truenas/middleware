from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = [
    "SystemBootIdArgs",
    "SystemBootIdResult",
    "SystemReadyArgs",
    "SystemReadyResult",
    "SystemRebootArgs",
    "SystemRebootResult",
    "SystemShutdownArgs",
    "SystemShutdownResult",
    "SystemStateArgs",
    "SystemStateResult",
    "SystemReadyAddedEvent",
    "SystemRebootAddedEvent",
    "SystemShutdownAddedEvent",
]


class SystemBootIdArgs(BaseModel):
    pass


class SystemBootIdResult(BaseModel):
    result: str
    """Unique identifier for the current system boot session."""


class SystemReadyArgs(BaseModel):
    pass


class SystemReadyResult(BaseModel):
    result: bool
    """Whether the system has completed startup and is ready for use."""


class SystemRebootOptions(BaseModel):
    delay: int | None = None
    """Delay in seconds before rebooting. `null` for immediate reboot."""


class SystemRebootArgs(BaseModel):
    reason: NonEmptyString
    """Reason for the system reboot."""
    options: SystemRebootOptions = Field(default_factory=SystemRebootOptions)
    """Options for controlling the reboot process."""


class SystemRebootResult(BaseModel):
    result: None
    """Returns `null` on successful reboot initiation."""


class SystemShutdownOptions(BaseModel):
    delay: int | None = None
    """Delay in seconds before shutting down. `null` for immediate shutdown."""


class SystemShutdownArgs(BaseModel):
    reason: NonEmptyString
    """Reason for the system shutdown."""
    options: SystemShutdownOptions = Field(default_factory=SystemShutdownOptions)
    """Options for controlling the shutdown process."""


class SystemShutdownResult(BaseModel):
    result: None
    """Returns `null` on successful shutdown initiation."""


class SystemStateArgs(BaseModel):
    pass


class SystemStateResult(BaseModel):
    result: Literal["BOOTING", "READY", "SHUTTING_DOWN"]
    """Current system state indicating boot status or shutdown process."""


class SystemReadyAddedEvent(BaseModel):
    pass


class SystemRebootAddedEvent(BaseModel):
    fields: "SystemRebootAddedEventFields"
    """Event fields."""


class SystemRebootAddedEventFields(BaseModel):
    reason: str
    """Reason for the system reboot."""


class SystemShutdownAddedEvent(BaseModel):
    pass
