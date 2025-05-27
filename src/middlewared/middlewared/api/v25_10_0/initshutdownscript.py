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
    timeout: int = 10
    """An integer time in seconds that the system should wait for the execution of the script/command.

    A hard limit for a timeout is configured by the base OS, so when a script/command is set to execute on SHUTDOWN, \
    the hard limit configured by the base OS is changed adding the timeout specified by script/command so it can be \
    ensured that it executes as desired and is not interrupted by the base OS's limit.
    """
    comment: Annotated[str, Field(max_length=255)] = ""


class InitShutdownScriptEntry(InitShutdownScriptCreate):
    id: int


class InitShutdownScriptUpdate(InitShutdownScriptCreate, metaclass=ForUpdateMetaclass):
    pass


class InitShutdownScriptCreateArgs(BaseModel):
    data: InitShutdownScriptCreate


class InitShutdownScriptCreateResult(BaseModel):
    result: InitShutdownScriptEntry


class InitShutdownScriptUpdateArgs(BaseModel):
    id: int
    data: InitShutdownScriptUpdate


class InitShutdownScriptUpdateResult(BaseModel):
    result: InitShutdownScriptEntry


class InitShutdownScriptDeleteArgs(BaseModel):
    id: int


class InitShutdownScriptDeleteResult(BaseModel):
    result: Literal[True]
    """Always return `True`."""  # FIXME: Should return False or raise exception if no record was deleted.
