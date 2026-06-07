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
]


class SystemBootIdArgs(BaseModel):
    pass


class SystemBootIdResult(BaseModel):
    result: str = Field(description="Unique identifier for the current system boot session.")


class SystemReadyArgs(BaseModel):
    pass


class SystemReadyResult(BaseModel):
    result: bool = Field(description="Whether the system has completed startup and is ready for use.")


class SystemRebootOptions(BaseModel):
    delay: int | None = Field(
        default=None,
        description="Delay in seconds before rebooting. `null` for immediate reboot.",
    )


class SystemRebootArgs(BaseModel):
    reason: NonEmptyString = Field(description="Reason for the system reboot.")
    options: SystemRebootOptions = Field(
        default_factory=SystemRebootOptions,
        description="Options for controlling the reboot process.",
    )


class SystemRebootResult(BaseModel):
    result: None = Field(description="Returns `null` on successful reboot initiation.")


class SystemShutdownOptions(BaseModel):
    delay: int | None = Field(
        default=None,
        description="Delay in seconds before shutting down. `null` for immediate shutdown.",
    )


class SystemShutdownArgs(BaseModel):
    reason: NonEmptyString = Field(description="Reason for the system shutdown.")
    options: SystemShutdownOptions = Field(
        default_factory=SystemShutdownOptions,
        description="Options for controlling the shutdown process.",
    )


class SystemShutdownResult(BaseModel):
    result: None = Field(description="Returns `null` on successful shutdown initiation.")


class SystemStateArgs(BaseModel):
    pass


class SystemStateResult(BaseModel):
    result: Literal["BOOTING", "READY", "SHUTTING_DOWN"] = Field(
        description="Current system state indicating boot status or shutdown process.",
    )
