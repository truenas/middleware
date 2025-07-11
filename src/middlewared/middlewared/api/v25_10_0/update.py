from typing import Literal

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString,
)


__all__ = [
    "UpdateEntry", "UpdateUpdateArgs", "UpdateUpdateResult",
    "UpdateProfileChoicesArgs", "UpdateProfileChoicesResult",
    "UpdateStatusArgs", "UpdateStatusResult", "UpdateStatusChangedEvent",
    "UpdateAvailableVersionsArgs", "UpdateAvailableVersionsResult",
    "UpdateDownloadArgs", "UpdateDownloadResult",
    "UpdateFileArgs", "UpdateFileResult",
    "UpdateManualArgs", "UpdateManualResult",
    "UpdateRunArgs", "UpdateRunResult",
]


class UpdateEntry(BaseModel):
    id: int
    autocheck: bool
    """Automatically check and download updates every night."""
    profile: str
    """Update profile used for the system."""


class UpdateUpdate(UpdateEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class UpdateUpdateArgs(BaseModel):
    data: UpdateUpdate


class UpdateUpdateResult(BaseModel):
    result: UpdateEntry


class UpdateProfileChoicesArgs(BaseModel):
    pass


class UpdateProfileChoicesResult(BaseModel):
    result: dict[str, "UpdateProfileChoice"]


class UpdateProfileChoice(BaseModel):
    name: str
    """Profile name."""
    footnote: str
    """Profile footnote."""
    description: LongString
    """Profile description."""
    available: bool
    """Whether profile is available for selection."""


class UpdateStatusArgs(BaseModel):
    pass


class UpdateStatusCurrentVersion(BaseModel):
    train: str
    """Train name."""
    profile: str
    """Update profile assigned for the version."""
    matches_profile: bool
    """Whether the system version running matches the configured update profile."""


class UpdateStatusNewVersion(BaseModel):
    version: str
    """Newly available version number."""
    manifest: dict
    release_notes_url: LongString
    """Release notes URL."""


class UpdateStatusStatus(BaseModel):
    current_version: UpdateStatusCurrentVersion
    """Currently running system version information."""
    new_version: UpdateStatusNewVersion | None
    """New system version information (or `null` if no new system version is available)."""


class UpdateDownloadProgress(BaseModel):
    percent: float
    description: LongString


class UpdateStatus(BaseModel):
    code: Literal['NORMAL', 'ERROR', 'REBOOT_REQUIRED', 'HA_UNAVAILABLE']
    """
    Status code:
    * NORMAL - normal status, see `status` dictionary for details.
    * ERROR - an error occurred, see `error` for details.
    * REBOOT_REQUIRED - system update was already applied, system reboot is required.
    * HA_UNAVAILABLE - HA is configured but currently unavailable.
    """
    status: UpdateStatusStatus | None
    error: LongString | None
    update_download_progress: UpdateDownloadProgress | None
    """Current update download progress."""


class UpdateStatusResult(BaseModel):
    result: UpdateStatus


class UpdateStatusChangedEvent(BaseModel):
    status: UpdateStatus


class UpdateAvailableVersionsArgs(BaseModel):
    pass


class UpdateAvailableVersionsResult(BaseModel):
    result: list["UpdateAvailableVersion"]


class UpdateAvailableVersion(BaseModel):
    train: str
    """Train that provides this version."""
    version: UpdateStatusNewVersion


class UpdateDownloadArgs(BaseModel):
    train: str | None = None
    """Specifies the train from which to download the update. If both `train` and `version` are `null``, the most \
    recent version that matches the currently selected update profile is used."""
    version: str | None = None


class UpdateDownloadResult(BaseModel):
    result: bool


class UpdateFileOptions(BaseModel):
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted. In that case, re-uploading the file \
    is not necessary."""
    destination: str | None = None
    """Create a temporary location by default."""


class UpdateFileArgs(BaseModel):
    options: UpdateFileOptions = UpdateFileOptions()


class UpdateFileResult(BaseModel):
    result: None


class UpdateManualOptions(BaseModel):
    dataset_name: str | None = None
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted."""
    cleanup: bool = True
    """If set to `false`, the manual update file won't be removed on update success and newly created BE won't be \
    removed on update failure (useful for debugging purposes)."""


class UpdateManualArgs(BaseModel):
    path: str
    """The absolute path to the update file."""
    options: UpdateManualOptions = UpdateManualOptions()


class UpdateManualResult(BaseModel):
    result: None


class UpdateRunAttrs(BaseModel):
    dataset_name: str | None = None
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted. In that case, update process will \
    be continued using an already downloaded file without performing any extra checks."""
    train: str | None = None
    """Specifies the train from which to download the update. If both `train` and `version` are `null``, the most \
    recent version that matches the currently selected update profile is used."""
    version: str | None = None
    reboot: bool = False


class UpdateRunArgs(BaseModel):
    attrs: UpdateRunAttrs = UpdateRunAttrs()


class UpdateRunResult(BaseModel):
    result: Literal[True]
