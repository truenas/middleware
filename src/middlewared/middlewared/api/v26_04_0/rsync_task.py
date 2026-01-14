from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString
from .common import CronModel
from .keychain import KeychainCredentialEntry

__all__ = ["RsyncTaskEntry",
           "RsyncTaskCreateArgs", "RsyncTaskCreateResult",
           "RsyncTaskUpdateArgs", "RsyncTaskUpdateResult",
           "RsyncTaskDeleteArgs", "RsyncTaskDeleteResult",
           "RsyncTaskRunArgs", "RsyncTaskRunResult"]

RSYNC_PATH_LIMIT = 1023


class RsyncTaskSchedule(CronModel):
    minute: str = "00"
    """Minute when the rsync task should run (cron format)."""


class RsyncTaskEntry(BaseModel):
    id: int
    """Unique identifier for the rsync task."""
    path: str = Field(max_length=RSYNC_PATH_LIMIT)
    """Local filesystem path to synchronize."""
    dataset: NonEmptyString | None
    """The ZFS dataset name that contains the rsync task path. This is the dataset where the task data is stored. \
    Returns `null` if the path is not on a ZFS dataset. This is a read-only field that is automatically populated \
    based on "path"."""
    relative_path: str | None
    """The path of the task relative to the dataset mountpoint. For example, if the task path is \
    `/mnt/tank/rsync/data` and the dataset `tank/rsync` is mounted at `/mnt/tank/rsync`, then the relative path is \
    "data". An empty string indicates the task is at the dataset root. Returns `null` if the path is not on a ZFS \
    dataset. This is a read-only field that is automatically populated based on "path"."""
    user: str
    """Username to run the rsync task as."""
    mode: Literal["MODULE", "SSH"] = "MODULE"
    """Operating mechanism for Rsync, i.e. Rsync Module mode or Rsync SSH mode."""
    remotehost: str | None = None
    """IP address or hostname of the remote system. If username differs on the remote host, "username@remote_host" \
    format should be used."""
    remoteport: int | None = None
    """Port number for SSH connection. Only applies when `mode` is SSH."""
    remotemodule: str | None = None
    """Name of remote module, this attribute should be specified when `mode` is set to MODULE."""
    ssh_credentials: KeychainCredentialEntry | None = None
    """In SSH mode, if `ssh_credentials` (a keychain credential of `SSH_CREDENTIALS` type) is specified then it is \
    used to connect to the remote host. If it is not specified, then keys in `user`'s .ssh directory are used."""
    remotepath: str = ""
    """Path on the remote system to synchronize with."""
    direction: Literal["PULL", "PUSH"] = "PUSH"
    """Specify if data should be PULLED or PUSHED from the remote system."""
    desc: str = ""
    """Description of the rsync task."""
    schedule: RsyncTaskSchedule = Field(default_factory=RsyncTaskSchedule)
    """Cron schedule for when the rsync task should run."""
    recursive: bool = True
    """Recursively transfer subdirectories."""
    times: bool = True
    """Preserve modification times of files."""
    compress: bool = True
    """Reduce the size of the data to be transmitted."""
    archive: bool = False
    """Make rsync run recursively, preserving symlinks, permissions, modification times, group, and special files."""
    delete: bool = False
    """Delete files in the destination directory that do not exist in the source directory."""
    quiet: bool = False
    """Suppress informational messages from rsync."""
    preserveperm: bool = False
    """Preserve original file permissions."""
    preserveattr: bool = False
    """Preserve extended attributes of files."""
    delayupdates: bool = True
    """Delay updating destination files until all transfers are complete."""
    extra: list[str] = Field(default_factory=list)
    """Array of additional rsync command-line options."""
    enabled: bool = True
    """Whether this rsync task is enabled."""
    locked: bool
    """Whether this rsync task is currently locked (running)."""
    job: dict | None
    """Information about the currently running job. `null` if no job is running."""


class RsyncTaskCreate(RsyncTaskEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    ssh_credentials: int | None = None
    """Keychain credential ID for SSH authentication. `null` to use user's SSH keys."""
    validate_rpath: bool = True
    """Validate the existence of the remote path."""
    ssh_keyscan: bool = False
    """Automatically add remote host key to user's known_hosts file."""
    locked: Excluded = excluded_field()
    job: Excluded = excluded_field()


class RsyncTaskCreateArgs(BaseModel):
    rsync_task_create: RsyncTaskCreate
    """Configuration for creating a new rsync task."""


class RsyncTaskCreateResult(BaseModel):
    result: RsyncTaskEntry
    """The newly created rsync task configuration."""


class RsyncTaskUpdate(RsyncTaskCreate, metaclass=ForUpdateMetaclass):
    pass


class RsyncTaskUpdateArgs(BaseModel):
    id: int
    """ID of the rsync task to update."""
    rsync_task_update: RsyncTaskUpdate
    """Updated configuration for the rsync task."""


class RsyncTaskUpdateResult(BaseModel):
    result: RsyncTaskEntry
    """The updated rsync task configuration."""


class RsyncTaskDeleteArgs(BaseModel):
    id: int
    """ID of the rsync task to delete."""


class RsyncTaskDeleteResult(BaseModel):
    result: bool
    """Whether the rsync task was successfully deleted."""


class RsyncTaskRunArgs(BaseModel):
    id: int
    """ID of the rsync task to run immediately."""


class RsyncTaskRunResult(BaseModel):
    result: None
    """Returns `null` on successful rsync task execution."""
