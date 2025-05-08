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
    minute: str = "00"


class RsyncTaskEntry(BaseModel):
    id: int
    path: str = Field(max_length=RSYNC_PATH_LIMIT)
    "See the comment in Rsyncmod about `path` length limits."
    user: str
    mode: Literal["MODULE", "SSH"] = "MODULE"
    "different operating mechanisms for Rsync i.e Rsync Module mode / Rsync SSH mode"
    remotehost: str | None = None
    """ip address or hostname of the remote system. If username differs on the remote host, "username@remote_host"
    format should be used."""
    remoteport: int | None = None
    remotemodule: str | None = None
    "name of remote module, this attribute should be specified when `mode` is set to MODULE."
    ssh_credentials: KeychainCredentialEntry | None
    """In SSH mode, if `ssh_credentials` (a keychain credential of `SSH_CREDENTIALS` type) is specified then it is used
    to connect to the remote host. If it is not specified, then keys in `user`'s .ssh directory are used."""
    remotepath: str
    "will automatically add remote host key to user's known_hosts file"
    direction: Literal["PULL", "PUSH"] = "PUSH"
    "specifies if data should be PULLED or PUSHED from the remote system"
    desc: str = ""
    schedule: RsyncTaskSchedule = Field(default_factory=RsyncTaskSchedule)
    recursive: bool = True
    times: bool = True
    compress: bool = True
    "when set reduces the size of the data which is to be transmitted."
    archive: bool = False
    """when set makes rsync run recursively, preserving symlinks, permissions, modification times, group, and special
    files."""
    delete: bool = False
    "when set deletes files in the destination directory which do not exist in the source directory."
    quiet: bool = False
    preserveperm: bool = False
    "when set preserves original file permissions."
    preserveattr: bool = False
    delayupdates: bool = True
    extra: list[str] = Field(default_factory=list)
    enabled: bool = True
    locked: bool
    job: dict | None


class RsyncTaskCreate(RsyncTaskEntry):
    id: Excluded = excluded_field()
    ssh_credentials: int | None = None
    "the path on the remote system."
    validate_rpath: bool = True
    "boolean which when sets validates the existence of the remote path"
    ssh_keyscan: bool = False
    locked: Excluded = excluded_field()
    job: Excluded = excluded_field()


class RsyncTaskCreateArgs(BaseModel):
    rsync_task_create: RsyncTaskCreate


class RsyncTaskCreateResult(BaseModel):
    result: RsyncTaskEntry


class RsyncTaskUpdate(RsyncTaskCreate, metaclass=ForUpdateMetaclass):
    pass


class RsyncTaskUpdateArgs(BaseModel):
    id: int
    rsync_task_update: RsyncTaskUpdate


class RsyncTaskUpdateResult(BaseModel):
    result: RsyncTaskEntry


class RsyncTaskDeleteArgs(BaseModel):
    id: int


class RsyncTaskDeleteResult(BaseModel):
    result: bool


class RsyncTaskRunArgs(BaseModel):
    id: int


class RsyncTaskRunResult(BaseModel):
    result: None
