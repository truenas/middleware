from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = [
    "ServiceEntry", "ServiceReloadArgs", "ServiceReloadResult", "ServiceRestartArgs", "ServiceRestartResult",
    "ServiceStartArgs", "ServiceStartResult", "ServiceStartedArgs", "ServiceStartedResult",
    "ServiceStartedOrEnabledArgs", "ServiceStartedOrEnabledResult", "ServiceStopArgs", "ServiceStopResult",
    "ServiceUpdateArgs", "ServiceUpdateResult", "ServiceControlArgs", "ServiceControlResult",
]


class ServiceEntry(BaseModel):
    id: int
    service: str
    enable: bool
    state: str
    pids: list[int]


class ServiceOptions(BaseModel):
    ha_propagate: bool = True
    silent: bool = True
    """Return `false` instead of an error if the operation fails."""
    timeout: int | None = 120


class ServiceUpdate(BaseModel):
    enable: bool
    """Whether the service should start on boot."""


class ServiceControlArgs(BaseModel):
    verb: Literal["START", "STOP", "RESTART", "RELOAD"]
    service: str
    options: ServiceOptions = Field(default_factory=ServiceOptions)


class ServiceControlResult(BaseModel):
    result: bool
    """
    For "START", "RESTART", "RELOAD", indicate whether the service is running after performing the operation.
    For "STOP", indicate whether the service was successfully stopped.
    """


class ServiceReloadArgs(BaseModel):
    service: str
    options: ServiceOptions = Field(default_factory=ServiceOptions)


class ServiceReloadResult(BaseModel):
    result: bool
    """The service is running after reload."""


class ServiceRestartArgs(BaseModel):
    service: str
    options: ServiceOptions = Field(default_factory=ServiceOptions)


class ServiceRestartResult(BaseModel):
    result: bool
    """The service is running after the restart."""


class ServiceStartArgs(BaseModel):
    service: str
    options: ServiceOptions = Field(default_factory=ServiceOptions)


class ServiceStartResult(BaseModel):
    result: bool
    """`true` if the service started successfully."""


class ServiceStartedArgs(BaseModel):
    service: str


class ServiceStartedResult(BaseModel):
    result: bool
    """Service is running."""


class ServiceStartedOrEnabledArgs(BaseModel):
    service: str


class ServiceStartedOrEnabledResult(BaseModel):
    result: bool
    """Service is running or set to start on boot."""


class ServiceStopArgs(BaseModel):
    service: str
    options: ServiceOptions = Field(default_factory=ServiceOptions)


class ServiceStopResult(BaseModel):
    result: bool
    """`true` if the service stopped successfully."""


class ServiceUpdateArgs(BaseModel):
    id_or_name: int | str
    """ID or name of the service to update."""
    service_update: ServiceUpdate


class ServiceUpdateResult(BaseModel):
    result: int
    """The service ID."""
