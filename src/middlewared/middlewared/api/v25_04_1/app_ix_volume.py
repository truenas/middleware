from middlewared.api.base import BaseModel, NonEmptyString


__all__ = ['AppIXVolumeEntry', 'AppIXVolumeExistsArgs', 'AppIXVolumeExistsResult']


class AppIXVolumeEntry(BaseModel):
    app_name: NonEmptyString
    name: NonEmptyString


class AppIXVolumeExistsArgs(BaseModel):
    name: NonEmptyString


class AppIXVolumeExistsResult(BaseModel):
    result: bool
