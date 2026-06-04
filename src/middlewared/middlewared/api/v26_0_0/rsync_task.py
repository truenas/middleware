from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass
from .common import CronModel
from .keychain import KeychainCredentialEntry

__all__ = ["RsyncTaskEntry",
           "RsyncTaskCreateArgs", "RsyncTaskCreateResult",
           "RsyncTaskUpdateArgs", "RsyncTaskUpdateResult",
           "RsyncTaskDeleteArgs", "RsyncTaskDeleteResult",
           "RsyncTaskRunArgs", "RsyncTaskRunResult"]

RSYNC_PATH_LIMIT = 1023


class RsyncTaskSchedule(CronModel):
    minute: str = Field(default="00", description="Minute when the rsync task should run (cron format).")


class RsyncTaskEntry(BaseModel):
    id: int = Field(description="Unique identifier for the rsync task.")
    path: str = Field(max_length=RSYNC_PATH_LIMIT, description="Local filesystem path to synchronize.")
    dataset: str | None = Field(
        description=(
            "The ZFS dataset containing the rsync task path (e.g., 'tank/data'). Returns `null` if the path cannot be "
            "resolved yet (encrypted dataset not unlocked, etc.). This is a read-only field automatically populated "
            "from \"path\"."
        ),
    )
    relative_path: str | None = Field(
        description=(
            "The path of the rsync task relative to the dataset mountpoint (e.g., 'backups/daily'). An empty string "
            "indicates the task path is at the dataset root. Returns `null` if the path cannot be resolved yet. This is"
            " a read-only field automatically populated from \"path\"."
        ),
    )
    user: str = Field(description="Username to run the rsync task as.")
    mode: Literal["MODULE", "SSH"] = Field(
        default="MODULE",
        description="Operating mechanism for Rsync, i.e. Rsync Module mode or Rsync SSH mode.",
    )
    remotehost: str | None = Field(
        default=None,
        description=(
            "IP address or hostname of the remote system. If username differs on the remote host, "
            "\"username@remote_host\" format should be used."
        ),
    )
    remoteport: int | None = Field(
        default=None,
        description="Port number for SSH connection. Only applies when `mode` is SSH.",
    )
    remotemodule: str | None = Field(
        default=None,
        description="Name of remote module, this attribute should be specified when `mode` is set to MODULE.",
    )
    ssh_credentials: KeychainCredentialEntry | None = Field(
        default=None,
        description=(
            "In SSH mode, if `ssh_credentials` (a keychain credential of `SSH_CREDENTIALS` type) is specified then it "
            "is used to connect to the remote host. If it is not specified, then keys in `user`'s .ssh directory are "
            "used."
        ),
    )
    remotepath: str = Field(default="", description="Path on the remote system to synchronize with.")
    direction: Literal["PULL", "PUSH"] = Field(
        default="PUSH",
        description="Specify if data should be PULLED or PUSHED from the remote system.",
    )
    desc: str = Field(default="", description="Description of the rsync task.")
    schedule: RsyncTaskSchedule = Field(
        default_factory=RsyncTaskSchedule,
        description="Cron schedule for when the rsync task should run.",
    )
    recursive: bool = Field(default=True, description="Recursively transfer subdirectories.")
    times: bool = Field(default=True, description="Preserve modification times of files.")
    compress: bool = Field(default=True, description="Reduce the size of the data to be transmitted.")
    archive: bool = Field(
        default=False,
        description=(
            "Make rsync run recursively, preserving symlinks, permissions, modification times, group, and special "
            "files."
        ),
    )
    delete: bool = Field(
        default=False,
        description="Delete files in the destination directory that do not exist in the source directory.",
    )
    quiet: bool = Field(default=False, description="Suppress informational messages from rsync.")
    preserveperm: bool = Field(default=False, description="Preserve original file permissions.")
    preserveattr: bool = Field(default=False, description="Preserve extended attributes of files.")
    delayupdates: bool = Field(
        default=True,
        description="Delay updating destination files until all transfers are complete.",
    )
    extra: list[str] = Field(default_factory=list, description="Array of additional rsync command-line options.")
    enabled: bool = Field(default=True, description="Whether this rsync task is enabled.")
    locked: bool = Field(description="Whether this rsync task is currently locked (running).")
    job: dict | None = Field(description="Information about the currently running job. `null` if no job is running.")


class RsyncTaskCreate(RsyncTaskEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    ssh_credentials: int | None = Field(
        default=None,
        description="Keychain credential ID for SSH authentication. `null` to use user's SSH keys.",
    )
    validate_rpath: bool = Field(default=True, description="Validate the existence of the remote path.")
    ssh_keyscan: bool = Field(
        default=False,
        description="Automatically add remote host key to user's known_hosts file.",
    )
    locked: Excluded = excluded_field()
    job: Excluded = excluded_field()


class RsyncTaskCreateArgs(BaseModel):
    rsync_task_create: RsyncTaskCreate = Field(description="Configuration for creating a new rsync task.")


class RsyncTaskCreateResult(BaseModel):
    result: RsyncTaskEntry = Field(description="The newly created rsync task configuration.")


class RsyncTaskUpdate(RsyncTaskCreate, metaclass=ForUpdateMetaclass):
    pass


class RsyncTaskUpdateArgs(BaseModel):
    id: int = Field(description="ID of the rsync task to update.")
    rsync_task_update: RsyncTaskUpdate = Field(description="Updated configuration for the rsync task.")


class RsyncTaskUpdateResult(BaseModel):
    result: RsyncTaskEntry = Field(description="The updated rsync task configuration.")


class RsyncTaskDeleteArgs(BaseModel):
    id: int = Field(description="ID of the rsync task to delete.")


class RsyncTaskDeleteResult(BaseModel):
    result: bool = Field(description="Whether the rsync task was successfully deleted.")


class RsyncTaskRunArgs(BaseModel):
    id: int = Field(description="ID of the rsync task to run immediately.")


class RsyncTaskRunResult(BaseModel):
    result: None = Field(description="Returns `null` on successful rsync task execution.")
