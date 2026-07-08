from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = [
    "BootEnvironmentEntry",
    "BootEnvironmentActivate",
    "BootEnvironmentActivateArgs",
    "BootEnvironmentActivateResult",
    "BootEnvironmentClone",
    "BootEnvironmentCloneArgs",
    "BootEnvironmentCloneResult",
    "BootEnvironmentDestroy",
    "BootEnvironmentDestroyArgs",
    "BootEnvironmentDestroyResult",
    "BootEnvironmentKeep",
    "BootEnvironmentKeepArgs",
    "BootEnvironmentKeepResult",
]


class BootEnvironmentEntry(BaseModel):
    id: NonEmptyString = Field(description="The name of the boot environment referenced by the boot environment tool.")
    dataset: NonEmptyString = Field(description="The name of the zfs dataset that represents the boot environment.")
    active: bool = Field(description="This is the currently running boot environment.")
    activated: bool = Field(description="Use this boot environment on next boot.")
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
    can_activate: bool = Field(description="The given boot environment may be activated.")


class BootEnvironmentActivate(BaseModel):
    id: NonEmptyString = Field(description="Name of the boot environment to activate for next boot.")


class BootEnvironmentActivateArgs(BaseModel):
    boot_environment_activate: BootEnvironmentActivate = Field(description="Boot environment activate parameters.")


class BootEnvironmentActivateResult(BaseModel):
    result: BootEnvironmentEntry = Field(description="The activated boot environment configuration.")


class BootEnvironmentClone(BaseModel):
    id: NonEmptyString = Field(description="Name of the existing boot environment to clone from.")
    target: NonEmptyString = Field(description="Name for the new cloned boot environment.")


class BootEnvironmentCloneArgs(BaseModel):
    boot_environment_clone: BootEnvironmentClone = Field(description="Boot environment clone parameters.")


class BootEnvironmentCloneResult(BaseModel):
    result: BootEnvironmentEntry = Field(description="The newly created cloned boot environment.")


class BootEnvironmentDestroy(BaseModel):
    id: NonEmptyString = Field(description="Name of the boot environment to destroy.")


class BootEnvironmentDestroyArgs(BaseModel):
    boot_environment_destroy: BootEnvironmentDestroy = Field(description="Boot environment destroy parameters.")


class BootEnvironmentDestroyResult(BaseModel):
    result: None = Field(description="Returns `null` when the boot environment is successfully destroyed.")


class BootEnvironmentKeep(BaseModel):
    id: NonEmptyString = Field(description="Name of the boot environment to modify.")
    value: bool = Field(description="Whether to protect this boot environment from automatic deletion.")


class BootEnvironmentKeepArgs(BaseModel):
    boot_environment_destroy: BootEnvironmentKeep = Field(description="Boot environment keep parameters.")


class BootEnvironmentKeepResult(BaseModel):
    result: BootEnvironmentEntry = Field(description="The updated boot environment with modified keep setting.")
