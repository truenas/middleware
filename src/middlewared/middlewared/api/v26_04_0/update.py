from __future__ import annotations

from typing import Literal

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString,
)


__all__ = [
    "UpdateConfigSafeEntry", "UpdateEntry",
    "UpdateUpdate", "UpdateUpdateArgs", "UpdateUpdateResult",
    "UpdateProfileChoice", "UpdateProfileChoicesArgs", "UpdateProfileChoicesResult",
    "UpdateStatus", "UpdateStatusCurrentVersion", "UpdateStatusError", "UpdateStatusNewVersion", "UpdateStatusStatus",
    "UpdateDownloadProgress", "UpdateStatusArgs", "UpdateStatusResult", "UpdateStatusChangedEvent",
    "UpdateAvailableVersion", "UpdateAvailableVersionsArgs", "UpdateAvailableVersionsResult",
    "UpdateDownloadArgs", "UpdateDownloadResult",
    "UpdateFileOptions", "UpdateFileArgs", "UpdateFileResult",
    "UpdateManualOptions", "UpdateManualArgs", "UpdateManualResult",
    "UpdateRunAttrs", "UpdateRunArgs", "UpdateRunResult",
]


class UpdateConfigSafeEntry(BaseModel):
    id: int
    """Unique identifier for the update configuration."""
    autocheck: bool
    """Automatically check and download updates every night."""
    profile: str | None
    """Update profile used for the system."""


class UpdateEntry(UpdateConfigSafeEntry):
    profile: str
    """Update profile used for the system."""


class UpdateUpdate(UpdateEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class UpdateUpdateArgs(BaseModel):
    data: UpdateUpdate
    """Updated configuration for system update settings."""


class UpdateUpdateResult(BaseModel):
    result: UpdateEntry
    """The updated system update configuration."""


class UpdateProfileChoicesArgs(BaseModel):
    pass


class UpdateProfileChoicesResult(BaseModel):
    result: dict[str, UpdateProfileChoice]
    """Object of available update profiles with their configuration details."""


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
    """Object containing detailed version information and metadata."""
    release_notes: LongString | None
    """Release notes."""
    release_notes_url: LongString
    """Release notes URL."""


class UpdateStatusStatus(BaseModel):
    current_version: UpdateStatusCurrentVersion
    """Currently running system version information."""
    new_version: UpdateStatusNewVersion | None
    """New system version information (or `null` if no new system version is available)."""


class UpdateStatusError(BaseModel):
    errname: str
    """Error code (i.e. ENONET)."""
    reason: LongString
    """Error text."""


class UpdateDownloadProgress(BaseModel):
    percent: float
    """Download completion percentage (0.0 to 100.0)."""
    description: LongString
    """Human-readable description of the current download activity."""
    version: str
    """Version number being downloaded."""


class UpdateStatus(BaseModel):
    code: Literal['NORMAL', 'ERROR']
    """
    Status code:
    * NORMAL - normal status, see `status` dictionary for details.
    * ERROR - an error occurred, see `error` for details.
    """
    status: UpdateStatusStatus | None
    """Detailed update status information. `null` if code is ERROR."""
    error: UpdateStatusError | None
    """Error message if code is ERROR. `null` otherwise."""
    update_download_progress: UpdateDownloadProgress | None
    """Current update download progress."""


class UpdateStatusResult(BaseModel):
    result: UpdateStatus
    """Current system update status and availability information."""


class UpdateStatusChangedEvent(BaseModel):
    status: UpdateStatus
    """Updated system update status information."""


class UpdateAvailableVersionsArgs(BaseModel):
    pass


class UpdateAvailableVersionsResult(BaseModel):
    result: list[UpdateAvailableVersion]
    """Array of available system update versions across all trains."""


class UpdateAvailableVersion(BaseModel):
    train: str
    """Train that provides this version."""
    version: UpdateStatusNewVersion
    """Detailed information about this available version."""


class UpdateDownloadArgs(BaseModel):
    train: str | None = None
    """Specifies the train from which to download the update. If both `train` and `version` are `null``, the most \
    recent version that matches the currently selected update profile is used."""
    version: str | None = None
    """Specific version to download. `null` to download the latest version from the specified train."""


class UpdateDownloadResult(BaseModel):
    result: bool
    """Whether the update download was successfully initiated."""


class UpdateFileOptions(BaseModel):
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted. In that case, re-uploading the file \
    is not necessary."""
    destination: str | None = None
    """Create a temporary location by default."""


class UpdateFileArgs(BaseModel):
    options: UpdateFileOptions = UpdateFileOptions()
    """Options for controlling the manual update file upload process."""


class UpdateFileResult(BaseModel):
    result: None
    """Returns `null` on successful update file upload and validation."""


class UpdateManualOptions(BaseModel):
    dataset_name: str | None = None
    """Name of the ZFS dataset to use for the new boot environment. `null` for automatic naming."""
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
    """Options for controlling the manual update process."""


class UpdateManualResult(BaseModel):
    result: None
    """Returns `null` on successful manual update initiation."""


class UpdateRunAttrs(BaseModel):
    dataset_name: str | None = None
    """Name of the ZFS dataset to use for the new boot environment. `null` for automatic naming."""
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted. In that case, update process will \
    be continued using an already downloaded file without performing any extra checks."""
    train: str | None = None
    """Specifies the train from which to download the update. If both `train` and `version` are `null``, the most \
    recent version that matches the currently selected update profile is used."""
    version: str | None = None
    """Specific version to update to. `null` to use the latest version from the specified train."""
    reboot: bool = False
    """Whether to automatically reboot the system after applying the update."""


class UpdateRunArgs(BaseModel):
    attrs: UpdateRunAttrs = UpdateRunAttrs()
    """Attributes controlling the system update execution process."""


class UpdateRunResult(BaseModel):
    result: Literal[True]
    """Always returns true on successful update process initiation."""
