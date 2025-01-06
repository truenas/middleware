from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass


__all__ = [
    "InitShutdownScriptEntry", "InitShutdownScriptCreateArgs", "InitShutdownScriptCreateResult",
    "InitShutdownScriptUpdateArgs", "InitShutdownScriptUpdateResult", "InitShutdownScriptDeleteArgs",
    "InitShutdownScriptDeleteResult", "InitShutdownScriptExecuteInitTasksArgs",
    "InitShutdownScriptExecuteInitTasksResult"
]


class InitShutdownScriptCreate(BaseModel):
    type: Literal["COMMAND", "SCRIPT"]
    command: str | None = ""
    script: str | None = ""
    when: Literal["PREINIT", "POSTINIT", "SHUTDOWN"]
    enabled: bool = True
    timeout: int = 10
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


class InitShutdownScriptExecuteInitTasksArgs(BaseModel):
    when: Literal["PREINIT", "POSTINIT", "SHUTDOWN"]


class InitShutdownScriptExecuteInitTasksResult(BaseModel):
    result: None
