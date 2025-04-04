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
    result: str


class SystemReadyArgs(BaseModel):
    pass


class SystemReadyResult(BaseModel):
    result: bool


class SystemRebootOptions(BaseModel):
    delay: int | None = None


class SystemRebootArgs(BaseModel):
    reason: NonEmptyString
    options: SystemRebootOptions = Field(default_factory=SystemRebootOptions)


class SystemRebootResult(BaseModel):
    result: None


class SystemShutdownOptions(BaseModel):
    delay: int | None = None


class SystemShutdownArgs(BaseModel):
    reason: NonEmptyString
    options: SystemShutdownOptions = Field(default_factory=SystemShutdownOptions)


class SystemShutdownResult(BaseModel):
    result: None


class SystemStateArgs(BaseModel):
    pass


class SystemStateResult(BaseModel):
    result: Literal["BOOTING", "READY", "SHUTTING_DOWN"]
