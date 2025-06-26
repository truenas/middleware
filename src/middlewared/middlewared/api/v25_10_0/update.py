from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, single_argument_result, NonEmptyString


__all__ = [
    "UpdateCheckAvailableArgs", "UpdateCheckAvailableResult", "UpdateDownloadArgs", "UpdateDownloadResult",
    "UpdateFileArgs", "UpdateFileResult", "UpdateGetAutoDownloadArgs", "UpdateGetAutoDownloadResult",
    "UpdateGetPendingArgs", "UpdateGetPendingResult", "UpdateGetTrainsArgs", "UpdateGetTrainsResult",
    "UpdateManualArgs", "UpdateManualResult", "UpdateSetAutoDownloadArgs", "UpdateSetAutoDownloadResult",
    "UpdateSetTrainArgs", "UpdateSetTrainResult", "UpdateUpdateArgs", "UpdateUpdateResult",
]


class UpdateCheckAvailable(BaseModel):
    train: str | None = None


class UpdateFile(BaseModel):
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted. In that case, re-uploading the file \
    is not necessary."""
    destination: str | None = None
    """Create a temporary location by default."""


class UpdateManual(BaseModel):
    dataset_name: str | None = None
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted."""
    cleanup: bool = True
    """If set to `false`, the manual update file won't be removed on update success and newly created BE won't be \
    removed on update failure (useful for debugging purposes)."""


class UpdateStatusAvailableChangesVersion(BaseModel):
    name: Literal["TrueNAS"]
    version: str


class UpdateStatusAvailableChanges(BaseModel):
    operation: Literal["upgrade"]
    old: UpdateStatusAvailableChangesVersion
    new: UpdateStatusAvailableChangesVersion


class UpdateStatusAvailable(BaseModel):
    status: Literal["AVAILABLE"]
    """An update is available."""
    changes: list[UpdateStatusAvailableChanges]
    notice: None
    notes: None
    release_notes_url: str | None
    changelog: str
    version: str
    """Version string of the available update version."""
    filename: str
    """Name of the update file available for download."""
    filesize: int
    """Size of the update file in bytes."""
    checksum: str


class UpdateStatusUnavailable(BaseModel):
    status: Literal["REBOOT_REQUIRED", "HA_UNAVAILABLE", "UNAVAILABLE"]
    """
    * `REBOOT_REQUIRED`: An update has already been applied.
    * `UNAVAILABLE`: No update available.
    * `HA_UNAVAILABLE`: HA is non-functional.
    """


class UpdateTrain(BaseModel):
    description: str


class UpdateUpdate(BaseModel):
    dataset_name: str | None = None
    resume: bool = False
    """Should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN` meaning \
    that an upgrade can be performed with a warning and that warning is accepted. In that case, update process will \
    be continued using an already downloaded file without performing any extra checks."""
    train: str | None = None
    reboot: bool = False


# ---------------   Args and Result models   ----------------- #


class UpdateCheckAvailableArgs(BaseModel):
    attrs: UpdateCheckAvailable = Field(default_factory=UpdateCheckAvailable)


class UpdateCheckAvailableResult(BaseModel):
    result: UpdateStatusAvailable | UpdateStatusUnavailable = Field(discriminator="status")


class UpdateDownloadArgs(BaseModel):
    pass


class UpdateDownloadResult(BaseModel):
    result: bool


class UpdateFileArgs(BaseModel):
    options: UpdateFile = Field(default_factory=UpdateFile)


class UpdateFileResult(BaseModel):
    result: None


class UpdateGetAutoDownloadArgs(BaseModel):
    pass


class UpdateGetAutoDownloadResult(BaseModel):
    result: bool


class UpdateGetPendingArgs(BaseModel):
    path: str | None = None


class UpdateGetPendingResult(BaseModel):
    result: list[UpdateStatusAvailableChanges]


class UpdateGetTrainsArgs(BaseModel):
    pass


@single_argument_result
class UpdateGetTrainsResult(BaseModel):
    trains: dict[str, UpdateTrain]
    current: str
    selected: str


class UpdateManualArgs(BaseModel):
    path: str
    """The absolute path to the update file."""
    options: UpdateManual = Field(default_factory=UpdateManual)


class UpdateManualResult(BaseModel):
    result: None


class UpdateSetAutoDownloadArgs(BaseModel):
    autocheck: bool


class UpdateSetAutoDownloadResult(BaseModel):
    result: None


class UpdateSetTrainArgs(BaseModel):
    train: NonEmptyString


class UpdateSetTrainResult(BaseModel):
    result: Literal[True]


class UpdateUpdateArgs(BaseModel):
    attrs: UpdateUpdate = Field(default_factory=UpdateUpdate)


class UpdateUpdateResult(BaseModel):
    result: Literal[True]
