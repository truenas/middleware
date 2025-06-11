from middlewared.api.base import BaseModel, NonEmptyString


__all__ = ['AppsIxVolumeEntry', 'AppsIxVolumeExistsArgs', 'AppsIxVolumeExistsResult']


class AppsIxVolumeEntry(BaseModel):
    app_name: NonEmptyString
    name: NonEmptyString


class AppsIxVolumeExistsArgs(BaseModel):
    name: NonEmptyString


class AppsIxVolumeExistsResult(BaseModel):
    result: bool
