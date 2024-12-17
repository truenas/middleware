from middlewared.api.base import BaseModel, LongString, single_argument_args


@single_argument_args("CloudSyncOneDriveListDrives")
class CloudSyncOneDriveListDrivesArgs(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    token: LongString


class CloudSyncOneDriveListDrivesResult(BaseModel):
    result: list
