from pydantic import Field

from middlewared.api.base import BaseModel, LongString, NonEmptyString
from .cloud_credential import CloudCredentialEntry
from .common import CronModel

__all__ = ["BaseCloudEntry"]


class CloudCron(CronModel):
    minute: str = "00"


class BaseCloudEntry(BaseModel):
    id: int
    description: str = ""
    """The name of the task to display in the UI"""
    path: str
    """The local path to back up beginning with `/mnt` or `/dev/zvol`"""
    credentials: CloudCredentialEntry
    """Cloud credentials to use for each backup"""
    attributes: dict
    """Additional information for each backup, e.g. bucket name"""
    schedule: CloudCron = Field(default_factory=CloudCron)
    """Cron schedule dictating when the task should run"""
    pre_script: LongString = ""
    """A Bash script to run immediately before every backup"""
    post_script: LongString = ""
    """A Bash script to run immediately after every backup if it succeeds"""
    snapshot: bool = False
    """Whether to create a temporary snapshot of the dataset before every backup"""
    include: list[NonEmptyString] = Field(default_factory=list)
    """Paths to pass to `restic backup --include`"""
    exclude: list[NonEmptyString] = Field(default_factory=list)
    """Paths to pass to `restic backup --exclude`"""
    args: LongString = ""
    """(Slated for removal)"""
    enabled: bool = True
    """Can enable/disable the task"""
    job: dict | None
    """Information regarding the task's job state, e.g. progress"""
    locked: bool
    """A locked task cannot run"""
