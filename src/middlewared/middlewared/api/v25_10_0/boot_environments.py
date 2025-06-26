from datetime import datetime

from middlewared.api.base import BaseModel, single_argument_args, NonEmptyString


__all__ = [
    "BootEnvironmentEntry", "BootEnvironmentActivateArgs", "BootEnvironmentActivateResult", "BootEnvironmentCloneArgs",
    "BootEnvironmentCloneResult", "BootEnvironmentDestroyArgs", "BootEnvironmentDestroyResult",
    "BootEnvironmentKeepArgs", "BootEnvironmentKeepResult",
]


class BootEnvironmentEntry(BaseModel):
    id: NonEmptyString
    """The name of the boot environment referenced by the boot environment tool."""
    dataset: NonEmptyString
    """The name of the zfs dataset that represents the boot environment."""
    active: bool
    """This is the currently running boot environment."""
    activated: bool
    """Use this boot environment on next boot."""
    created: datetime
    """The date when the boot environment was created."""
    used_bytes: int
    """The total amount of bytes used by the boot environment."""
    used: NonEmptyString
    """The boot environment's used space in human readable format."""
    keep: bool
    """When set to false, this makes the boot environment subject to \
    automatic deletion if the TrueNAS updater needs space for an update. \
    Otherwise, the updater will not delete this boot environment if it is \
    set to true."""
    can_activate: bool
    """The given boot environment may be activated."""


@single_argument_args("boot_environment_activate")
class BootEnvironmentActivateArgs(BaseModel):
    id: NonEmptyString


class BootEnvironmentActivateResult(BaseModel):
    result: BootEnvironmentEntry


@single_argument_args("boot_environment_clone")
class BootEnvironmentCloneArgs(BaseModel):
    id: NonEmptyString
    target: NonEmptyString


class BootEnvironmentCloneResult(BaseModel):
    result: BootEnvironmentEntry


@single_argument_args("boot_environment_destroy")
class BootEnvironmentDestroyArgs(BaseModel):
    id: NonEmptyString


class BootEnvironmentDestroyResult(BaseModel):
    result: None


@single_argument_args("boot_environment_destroy")
class BootEnvironmentKeepArgs(BaseModel):
    id: NonEmptyString
    value: bool


class BootEnvironmentKeepResult(BaseModel):
    result: BootEnvironmentEntry
