from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, single_argument_result, NonEmptyString, NotRequired


__all__ = [
    "UpdateCheckAvailableArgs", "UpdateCheckAvailableResult", "UpdateDownloadArgs", "UpdateDownloadResult",
    "UpdateFileArgs", "UpdateFileResult", "UpdateGetAutoDownloadArgs", "UpdateGetAutoDownloadResult",
    "UpdateGetPendingArgs", "UpdateGetPendingResult", "UpdateGetTrainsArgs", "UpdateGetTrainsResult",
    "UpdateManualArgs", "UpdateManualResult", "UpdateSetAutoDownloadArgs", "UpdateSetAutoDownloadResult",
    "UpdateSetTrainArgs", "UpdateSetTrainResult", "UpdateUpdateArgs", "UpdateUpdateResult",
]


class UpdateCheckAvailable(BaseModel):
    train: str = NotRequired


class UpdateFile(BaseModel):
    resume: bool = False
    destination: str | None = None


class UpdateManual(BaseModel):
    dataset_name: str | None = None
    resume: bool = False
    cleanup: bool = True


class UpdateStatusAvailableChangesVersion(BaseModel):
    name: Literal["TrueNAS"]
    version: str


class UpdateStatusAvailableChanges(BaseModel):
    operation: Literal["upgrade"]
    old: UpdateStatusAvailableChangesVersion
    new: UpdateStatusAvailableChangesVersion


class UpdateStatusAvailable(BaseModel):
    status: Literal["AVAILABLE"]
    changes: tuple[UpdateStatusAvailableChanges]
    notice: None
    notes: None
    release_notes_url: str | None
    changelog: str
    version: str
    filename: str
    filesize: str
    checksum: str


class UpdateStatusUnavailable(BaseModel):
    status: Literal["REBOOT_REQUIRED", "HA_UNAVAILABLE", "UNAVAILABLE"]


class UpdateTrain(BaseModel):
    description: str


class Update(BaseModel):
    dataset_name: str | None = None
    resume: bool = False
    train: str | None = None
    reboot: bool = False


###################   Args and Result models   #####################


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
    attrs: Update = Field(default_factory=Update)


class UpdateUpdateResult(BaseModel):
    result: Literal[True]
