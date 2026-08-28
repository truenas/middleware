from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass
from .common import CronModel


__all__ = [
    "CronJobEntry", "CronJobCreateArgs", "CronJobCreateResult", "CronJobUpdateArgs", "CronJobUpdateResult",
    "CronJobDeleteArgs", "CronJobDeleteResult", "CronJobRunArgs", "CronJobRunResult"
]


class CronJobSchedule(CronModel):
    minute: str = Field(default="00", description="\"00\" - \"59\"")


class CronJobCreate(BaseModel):
    enabled: bool = Field(default=True, description="Whether the cron job is active and will be executed.")
    stderr: bool = Field(
        default=False,
        description="Whether to IGNORE standard error (if `false`, it will be added to email).",
    )
    stdout: bool = Field(
        default=True,
        description="Whether to IGNORE standard output (if `false`, it will be added to email).",
    )
    schedule: CronJobSchedule = Field(
        default=CronJobSchedule(),
        description="Cron schedule configuration for when the job runs.",
    )
    command: str = Field(description="Shell command or script to execute.")
    description: str = Field(default="", description="Human-readable description of what this cron job does.")
    user: str = Field(description="System user account to run the command as.")


class CronJobEntry(CronJobCreate):
    id: int = Field(description="Unique identifier for the cron job.")


class CronJobUpdate(CronJobCreate, metaclass=ForUpdateMetaclass):
    pass


class CronJobCreateArgs(BaseModel):
    data: CronJobCreate = Field(description="Cron job configuration data for the new job.")


class CronJobCreateResult(BaseModel):
    result: CronJobEntry = Field(description="The created cron job configuration.")


class CronJobUpdateArgs(BaseModel):
    id: int = Field(description="ID of the cron job to update.")
    data: CronJobUpdate = Field(description="Updated cron job configuration data.")


class CronJobUpdateResult(BaseModel):
    result: CronJobEntry = Field(description="The updated cron job configuration.")


class CronJobDeleteArgs(BaseModel):
    id: int = Field(description="ID of the cron job to delete.")


class CronJobDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the cron job is successfully deleted.")


class CronJobRunArgs(BaseModel):
    id: int = Field(description="ID of the cron job to run immediately.")
    skip_disabled: bool = Field(default=False, description="Whether to skip execution if the cron job is disabled.")


class CronJobRunResult(BaseModel):
    result: None = Field(description="Returns `null` when the cron job is successfully started.")
