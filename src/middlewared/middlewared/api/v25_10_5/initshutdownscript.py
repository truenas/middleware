from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass


__all__ = [
    "InitShutdownScriptEntry", "InitShutdownScriptCreateArgs", "InitShutdownScriptCreateResult",
    "InitShutdownScriptUpdateArgs", "InitShutdownScriptUpdateResult", "InitShutdownScriptDeleteArgs",
    "InitShutdownScriptDeleteResult",
]


class InitShutdownScriptCreate(BaseModel):
    type: Literal["COMMAND", "SCRIPT"] = Field(
        description=(
            "Type of init/shutdown script to execute.\n"
            "\n"
            "* `COMMAND`: Execute a single command\n"
            "* `SCRIPT`: Execute a script file"
        ),
    )
    command: str | None = Field(default="", description="Must be given if `type=\"COMMAND\"`.")
    script: str | None = Field(default="", description="Must be given if `type=\"SCRIPT\"`.")
    when: Literal["PREINIT", "POSTINIT", "SHUTDOWN"] = Field(
        description=(
            "* \"PREINIT\": Early in the boot process before all services have started.\n"
            "* \"POSTINIT\": Late in the boot process when most services have started.\n"
            "* \"SHUTDOWN\": On shutdown."
        ),
    )
    enabled: bool = Field(default=True, description="Whether the init/shutdown script is enabled to execute.")
    timeout: int = Field(
        default=10,
        description=(
            "An integer time in seconds that the system should wait for the execution of the script/command.\n"
            "\n"
            "A hard limit for a timeout is configured by the base OS, so when a script/command is set to execute on "
            "SHUTDOWN, the hard limit configured by the base OS is changed adding the timeout specified by "
            "script/command so it can be ensured that it executes as desired and is not interrupted by the base OS's "
            "limit."
        ),
    )
    comment: Annotated[str, Field(max_length=255)] = Field(
        default="",
        description="Optional comment describing the purpose of this script.",
    )


class InitShutdownScriptEntry(InitShutdownScriptCreate):
    id: int = Field(description="Unique identifier for the init/shutdown script.")


class InitShutdownScriptUpdate(InitShutdownScriptCreate, metaclass=ForUpdateMetaclass):
    pass


class InitShutdownScriptCreateArgs(BaseModel):
    data: InitShutdownScriptCreate = Field(description="Init/shutdown script configuration data for creation.")


class InitShutdownScriptCreateResult(BaseModel):
    result: InitShutdownScriptEntry = Field(description="The created init/shutdown script configuration.")


class InitShutdownScriptUpdateArgs(BaseModel):
    id: int = Field(description="ID of the init/shutdown script to update.")
    data: InitShutdownScriptUpdate = Field(description="Updated init/shutdown script configuration data.")


class InitShutdownScriptUpdateResult(BaseModel):
    result: InitShutdownScriptEntry = Field(description="The updated init/shutdown script configuration.")


class InitShutdownScriptDeleteArgs(BaseModel):
    id: int = Field(description="ID of the init/shutdown script to delete.")


class InitShutdownScriptDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Always return `True`.")
