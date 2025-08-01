from typing import Literal

from middlewared.api.base import BaseModel, ForUpdateMetaclass
from .common import CronModel


__all__ = [
    "CronJobEntry", "CronJobCreateArgs", "CronJobCreateResult", "CronJobUpdateArgs", "CronJobUpdateResult",
    "CronJobDeleteArgs", "CronJobDeleteResult", "CronJobRunArgs", "CronJobRunResult"
]


class CronJobSchedule(CronModel):
    minute: str = "00"
    """"00" - "59\""""


class CronJobCreate(BaseModel):
    enabled: bool = True
    """Whether the cron job is active and will be executed."""
    stderr: bool = False
    """Whether to redirect standard error output to email."""
    stdout: bool = True
    """Whether to redirect standard output to email."""
    schedule: CronJobSchedule = CronJobSchedule()
    """Cron schedule configuration for when the job runs."""
    command: str
    """Shell command or script to execute."""
    description: str = ""
    """Human-readable description of what this cron job does."""
    user: str
    """System user account to run the command as."""


class CronJobEntry(CronJobCreate):
    id: int
    """Unique identifier for the cron job."""


class CronJobUpdate(CronJobCreate, metaclass=ForUpdateMetaclass):
    pass


class CronJobCreateArgs(BaseModel):
    data: CronJobCreate
    """Cron job configuration data for the new job."""


class CronJobCreateResult(BaseModel):
    result: CronJobEntry
    """The created cron job configuration."""


class CronJobUpdateArgs(BaseModel):
    id: int
    """ID of the cron job to update."""
    data: CronJobUpdate
    """Updated cron job configuration data."""


class CronJobUpdateResult(BaseModel):
    result: CronJobEntry
    """The updated cron job configuration."""


class CronJobDeleteArgs(BaseModel):
    id: int
    """ID of the cron job to delete."""


class CronJobDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the cron job is successfully deleted."""


class CronJobRunArgs(BaseModel):
    id: int
    """ID of the cron job to run immediately."""
    skip_disabled: bool = False
    """Whether to skip execution if the cron job is disabled."""


class CronJobRunResult(BaseModel):
    result: None
    """Returns `null` when the cron job is successfully started."""
