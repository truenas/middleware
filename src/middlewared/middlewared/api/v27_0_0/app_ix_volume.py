from middlewared.api.base import BaseModel, NonEmptyString


__all__ = ['AppsIxVolumeEntry', 'AppsIxVolumeExistsArgs', 'AppsIxVolumeExistsResult']


class AppsIxVolumeEntry(BaseModel):
    app_name: NonEmptyString
    """Name of the application that owns this iX volume."""
    name: NonEmptyString
    """Name of the iX volume used for persistent storage."""


class AppsIxVolumeExistsArgs(BaseModel):
    name: NonEmptyString
    """Name of the iX volume to check for existence."""


class AppsIxVolumeExistsResult(BaseModel):
    result: bool
    """Returns `true` if the iX volume exists, `false` otherwise."""
