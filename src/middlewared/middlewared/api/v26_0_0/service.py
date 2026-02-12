from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = [
    "ServiceEntry", "ServiceStartedArgs", "ServiceStartedResult",
    "ServiceStartedOrEnabledArgs", "ServiceStartedOrEnabledResult",
    "ServiceUpdateArgs", "ServiceUpdateResult", "ServiceControlArgs", "ServiceControlResult",
]


class ServiceEntry(BaseModel):
    id: int
    """Unique identifier for the service."""
    service: str
    """Name of the system service."""
    enable: bool
    """Whether the service is enabled to start on boot."""
    state: str
    """Current state of the service (e.g., 'RUNNING', 'STOPPED')."""
    pids: list[int]
    """Array of process IDs associated with this service."""


class ServiceOptions(BaseModel):
    ha_propagate: bool = True
    """Whether to propagate the service operation to the HA peer in a high-availability setup."""
    silent: bool = True
    """Return `false` instead of an error if the operation fails."""
    timeout: int | None = 120
    """Maximum time in seconds to wait for the service operation to complete. `null` for no timeout."""


class ServiceUpdate(BaseModel):
    enable: bool
    """Whether the service should start on boot."""


class ServiceControlArgs(BaseModel):
    verb: Literal["START", "STOP", "RESTART", "RELOAD"]
    """The service operation to perform."""
    service: str
    """Name of the service to control."""
    options: ServiceOptions = Field(default_factory=ServiceOptions)
    """Options for controlling the service operation behavior."""


class ServiceControlResult(BaseModel):
    result: bool
    """
    For "START", "RESTART", "RELOAD", indicate whether the service is running after performing the operation.
    For "STOP", indicate whether the service was successfully stopped.
    """


class ServiceStartedArgs(BaseModel):
    service: str
    """Name of the service to check if running."""


class ServiceStartedResult(BaseModel):
    result: bool
    """Service is running."""


class ServiceStartedOrEnabledArgs(BaseModel):
    service: str
    """Name of the service to check if running or enabled."""


class ServiceStartedOrEnabledResult(BaseModel):
    result: bool
    """Service is running or set to start on boot."""


class ServiceUpdateArgs(BaseModel):
    id_or_name: int | str
    """ID or name of the service to update."""
    service_update: ServiceUpdate
    """Updated configuration for the service."""


class ServiceUpdateResult(BaseModel):
    result: int
    """The service ID."""
