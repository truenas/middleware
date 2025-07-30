from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass


__all__ = [
    "InitShutdownScriptEntry", "InitShutdownScriptCreateArgs", "InitShutdownScriptCreateResult",
    "InitShutdownScriptUpdateArgs", "InitShutdownScriptUpdateResult", "InitShutdownScriptDeleteArgs",
    "InitShutdownScriptDeleteResult",
]


class InitShutdownScriptCreate(BaseModel):
    type: Literal["COMMAND", "SCRIPT"]
    """Type of init/shutdown script to execute.

    * `COMMAND`: Execute a single command
    * `SCRIPT`: Execute a script file
    """
    command: str | None = ""
    """Must be given if `type="COMMAND"`."""
    script: str | None = ""
    """Must be given if `type="SCRIPT"`."""
    when: Literal["PREINIT", "POSTINIT", "SHUTDOWN"]
    """
    * "PREINIT": Early in the boot process before all services have started.
    * "POSTINIT": Late in the boot process when most services have started.
    * "SHUTDOWN": On shutdown.
    """
    enabled: bool = True
    """Whether the init/shutdown script is enabled to execute."""
    timeout: int = 10
    """An integer time in seconds that the system should wait for the execution of the script/command.

    A hard limit for a timeout is configured by the base OS, so when a script/command is set to execute on SHUTDOWN, \
    the hard limit configured by the base OS is changed adding the timeout specified by script/command so it can be \
    ensured that it executes as desired and is not interrupted by the base OS's limit.
    """
    comment: Annotated[str, Field(max_length=255)] = ""
    """Optional comment describing the purpose of this script."""


class InitShutdownScriptEntry(InitShutdownScriptCreate):
    id: int
    """Unique identifier for the init/shutdown script."""


class InitShutdownScriptUpdate(InitShutdownScriptCreate, metaclass=ForUpdateMetaclass):
    pass


class InitShutdownScriptCreateArgs(BaseModel):
    data: InitShutdownScriptCreate
    """Init/shutdown script configuration data for creation."""


class InitShutdownScriptCreateResult(BaseModel):
    result: InitShutdownScriptEntry
    """The created init/shutdown script configuration."""


class InitShutdownScriptUpdateArgs(BaseModel):
    id: int
    """ID of the init/shutdown script to update."""
    data: InitShutdownScriptUpdate
    """Updated init/shutdown script configuration data."""


class InitShutdownScriptUpdateResult(BaseModel):
    result: InitShutdownScriptEntry
    """The updated init/shutdown script configuration."""


class InitShutdownScriptDeleteArgs(BaseModel):
    id: int
    """ID of the init/shutdown script to delete."""


class InitShutdownScriptDeleteResult(BaseModel):
    result: Literal[True]
    """Always return `True`."""  # FIXME: Should return False or raise exception if no record was deleted.
