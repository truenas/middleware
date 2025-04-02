from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = ["SystemRebootArgs", "SystemRebootResult",
           "SystemShutdownArgs", "SystemShutdownResult"]


class SystemRebootOptions(BaseModel):
    delay: int | None = None


class SystemRebootArgs(BaseModel):
    reason: NonEmptyString
    options: SystemRebootOptions = Field(default=SystemRebootOptions())


class SystemRebootResult(BaseModel):
    result: None


class SystemShutdownOptions(BaseModel):
    delay: int | None = None


class SystemShutdownArgs(BaseModel):
    reason: NonEmptyString
    options: SystemShutdownOptions = Field(default=SystemShutdownOptions())


class SystemShutdownResult(BaseModel):
    result: None
