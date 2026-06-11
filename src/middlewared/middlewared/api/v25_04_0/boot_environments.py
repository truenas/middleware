from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, single_argument_args, NonEmptyString


class BootEnvironmentEntry(BaseModel):
    id: NonEmptyString = Field(description="The name of the boot environment referenced by the boot environment tool.")
    dataset: NonEmptyString = Field(description="The name of the zfs dataset that represents the boot environment.")
    active: bool = Field(description="If active is True, this is the currently running boot environment.")
    activated: bool = Field(description="If True, this will be the boot environment that is used at next boot.")
    created: datetime = Field(description="The date when the boot environment was created.")
    used_bytes: int = Field(description="The total amount of bytes used by the boot environment.")
    used: NonEmptyString = Field(description="The boot environment's used space in human readable format.")
    keep: bool = Field(
        description=(
            "When set to false, this makes the boot environment subject to automatic deletion if the TrueNAS updater "
            "needs space for an update. Otherwise, the updater will not delete this boot environment if it is set to "
            "true."
        ),
    )
    can_activate: bool = Field(description="If set to true, the given boot environment may be activated.")


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
