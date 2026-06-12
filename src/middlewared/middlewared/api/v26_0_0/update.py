from __future__ import annotations

from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    LongString,
    excluded_field,
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
    id: int = Field(description="Unique identifier for the update configuration.")
    autocheck: bool = Field(description="Automatically check and download updates every night.")
    profile: str | None = Field(description="Update profile used for the system.")


class UpdateEntry(UpdateConfigSafeEntry):
    profile: str = Field(description="Update profile used for the system.")


class UpdateUpdate(UpdateEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class UpdateUpdateArgs(BaseModel):
    data: UpdateUpdate = Field(description="Updated configuration for system update settings.")


class UpdateUpdateResult(BaseModel):
    result: UpdateEntry = Field(description="The updated system update configuration.")


class UpdateProfileChoicesArgs(BaseModel):
    pass


class UpdateProfileChoicesResult(BaseModel):
    result: dict[str, UpdateProfileChoice] = Field(
        description="Object of available update profiles with their configuration details.",
    )


class UpdateProfileChoice(BaseModel):
    name: str = Field(description="Profile name.")
    footnote: str = Field(description="Profile footnote.")
    description: LongString = Field(description="Profile description.")
    available: bool = Field(description="Whether profile is available for selection.")


class UpdateStatusArgs(BaseModel):
    pass


class UpdateStatusCurrentVersion(BaseModel):
    train: str = Field(description="Train name.")
    profile: str = Field(description="Update profile assigned for the version.")
    matches_profile: bool = Field(
        description="Whether the system version running matches the configured update profile.",
    )


class UpdateStatusNewVersion(BaseModel):
    version: str = Field(description="Newly available version number.")
    manifest: dict = Field(description="Object containing detailed version information and metadata.")
    release_notes: LongString | None = Field(description="Release notes.")
    release_notes_url: LongString = Field(description="Release notes URL.")


class UpdateStatusStatus(BaseModel):
    current_version: UpdateStatusCurrentVersion = Field(description="Currently running system version information.")
    new_version: UpdateStatusNewVersion | None = Field(
        description="New system version information (or `null` if no new system version is available).",
    )


class UpdateStatusError(BaseModel):
    errname: str = Field(description="Error code (i.e. ENONET).")
    reason: LongString = Field(description="Error text.")


class UpdateDownloadProgress(BaseModel):
    percent: float = Field(description="Download completion percentage (0.0 to 100.0).")
    description: LongString = Field(description="Human-readable description of the current download activity.")
    version: str = Field(description="Version number being downloaded.")


class UpdateStatus(BaseModel):
    code: Literal['NORMAL', 'ERROR'] = Field(
        description=(
            "Status code:\n"
            "* NORMAL - normal status, see `status` dictionary for details.\n"
            "* ERROR - an error occurred, see `error` for details."
        ),
    )
    status: UpdateStatusStatus | None = Field(
        description="Detailed update status information. `null` if code is ERROR.",
    )
    error: UpdateStatusError | None = Field(description="Error message if code is ERROR. `null` otherwise.")
    update_download_progress: UpdateDownloadProgress | None = Field(description="Current update download progress.")


class UpdateStatusResult(BaseModel):
    result: UpdateStatus = Field(description="Current system update status and availability information.")


class UpdateStatusChangedEvent(BaseModel):
    status: UpdateStatus = Field(description="Updated system update status information.")


class UpdateAvailableVersionsArgs(BaseModel):
    pass


class UpdateAvailableVersionsResult(BaseModel):
    result: list[UpdateAvailableVersion] = Field(
        description="Array of available system update versions across all trains.",
    )


class UpdateAvailableVersion(BaseModel):
    train: str = Field(description="Train that provides this version.")
    version: UpdateStatusNewVersion = Field(description="Detailed information about this available version.")


class UpdateDownloadArgs(BaseModel):
    train: str | None = Field(
        default=None,
        description=(
            "Specifies the train from which to download the update. If both `train` and `version` are `null``, the most"
            " recent version that matches the currently selected update profile is used."
        ),
    )
    version: str | None = Field(
        default=None,
        description="Specific version to download. `null` to download the latest version from the specified train.",
    )


class UpdateDownloadResult(BaseModel):
    result: bool = Field(description="Whether the update download was successfully initiated.")


class UpdateFileOptions(BaseModel):
    resume: bool = Field(
        default=False,
        description=(
            "Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` "
            "meaning that an upgrade can be performed with a warning and that warning is accepted. In that case, "
            "re-uploading the file is not necessary."
        ),
    )
    destination: str | None = Field(default=None, description="Create a temporary location by default.")


class UpdateFileArgs(BaseModel):
    options: UpdateFileOptions = Field(
        default=UpdateFileOptions(),
        description="Options for controlling the manual update file upload process.",
    )


class UpdateFileResult(BaseModel):
    result: None = Field(description="Returns `null` on successful update file upload and validation.")


class UpdateManualOptions(BaseModel):
    dataset_name: str | None = Field(
        default=None,
        description="Name of the ZFS dataset to use for the new boot environment. `null` for automatic naming.",
    )
    resume: bool = Field(
        default=False,
        description=(
            "Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` "
            "meaning that an upgrade can be performed with a warning and that warning is accepted."
        ),
    )
    cleanup: bool = Field(
        default=True,
        description=(
            "If set to `false`, the manual update file won't be removed on update success and newly created BE won't be"
            " removed on update failure (useful for debugging purposes)."
        ),
    )


class UpdateManualArgs(BaseModel):
    path: str = Field(description="The absolute path to the update file.")
    options: UpdateManualOptions = Field(
        default=UpdateManualOptions(),
        description="Options for controlling the manual update process.",
    )


class UpdateManualResult(BaseModel):
    result: None = Field(description="Returns `null` on successful manual update initiation.")


class UpdateRunAttrs(BaseModel):
    dataset_name: str | None = Field(
        default=None,
        description="Name of the ZFS dataset to use for the new boot environment. `null` for automatic naming.",
    )
    resume: bool = Field(
        default=False,
        description=(
            "Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` "
            "meaning that an upgrade can be performed with a warning and that warning is accepted. In that case, update"
            " process will be continued using an already downloaded file without performing any extra checks."
        ),
    )
    train: str | None = Field(
        default=None,
        description=(
            "Specifies the train from which to download the update. If both `train` and `version` are `null``, the most"
            " recent version that matches the currently selected update profile is used."
        ),
    )
    version: str | None = Field(
        default=None,
        description="Specific version to update to. `null` to use the latest version from the specified train.",
    )
    reboot: bool = Field(
        default=False,
        description="Whether to automatically reboot the system after applying the update.",
    )


class UpdateRunArgs(BaseModel):
    attrs: UpdateRunAttrs = Field(
        default=UpdateRunAttrs(),
        description="Attributes controlling the system update execution process.",
    )


class UpdateRunResult(BaseModel):
    result: Literal[True] = Field(description="Always returns true on successful update process initiation.")
