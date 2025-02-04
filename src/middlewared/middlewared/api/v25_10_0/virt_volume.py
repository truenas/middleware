import os
from typing import Literal

from pydantic import Field, field_validator

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)

__all__ = [
    'VirtVolumeEntry', 'VirtVolumeCreateArgs', 'VirtVolumeCreateResult',
    'VirtVolumeUpdateArgs', 'VirtVolumeUpdateResult', 'VirtVolumeDeleteArgs',
    'VirtVolumeDeleteResult', 'VirtVolumeImportISOArgs', 'VirtVolumeImportISOResult',
]


class VirtVolumeEntry(BaseModel):
    id: NonEmptyString
    name: NonEmptyString
    content_type: NonEmptyString
    created_at: str
    type: NonEmptyString
    config: dict
    used_by: list[NonEmptyString]


@single_argument_args('virt_volume_create')
class VirtVolumeCreateArgs(BaseModel):
    name: NonEmptyString
    content_type: Literal['BLOCK'] = 'BLOCK'
    size: int = Field(ge=512, default=1024)  # 1 gb default
    '''Size of volume in MB and it should at least be 512 MB'''


class VirtVolumeCreateResult(BaseModel):
    result: VirtVolumeEntry


class VirtVolumeUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    size: int = Field(ge=512)


class VirtVolumeUpdateArgs(BaseModel):
    id: NonEmptyString
    virt_volume_update: VirtVolumeUpdate


class VirtVolumeUpdateResult(BaseModel):
    result: VirtVolumeEntry


class VirtVolumeDeleteArgs(BaseModel):
    id: NonEmptyString


class VirtVolumeDeleteResult(BaseModel):
    result: Literal[True]


@single_argument_args('virt_volume_import_iso')
class VirtVolumeImportISOArgs(BaseModel):
    name: NonEmptyString
    '''Specify name of the newly created volume from the ISO specified'''
    iso_location: NonEmptyString | None = None
    upload_iso: bool = False

    @field_validator('iso_location')
    @classmethod
    def validate_iso_location(cls, v):
        if v and not os.path.exists(v):
            raise ValueError('Specified ISO location does not exist')
        return v


class VirtVolumeImportISOResult(BaseModel):
    result: VirtVolumeEntry
