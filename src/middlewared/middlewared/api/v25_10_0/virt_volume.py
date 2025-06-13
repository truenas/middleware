import re
from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, Field, field_validator, StringConstraints

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, match_validator, NonEmptyString, single_argument_args,
)

__all__ = [
    'VirtVolumeEntry', 'VirtVolumeCreateArgs', 'VirtVolumeCreateResult',
    'VirtVolumeUpdateArgs', 'VirtVolumeUpdateResult', 'VirtVolumeDeleteArgs',
    'VirtVolumeDeleteResult', 'VirtVolumeImportIsoArgs', 'VirtVolumeImportIsoResult',
    'VirtVolumeImportZvolArgs', 'VirtVolumeImportZvolResult'
]


RE_VOLUME_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9-._]*[A-Za-z0-9]$', re.IGNORECASE)
VOLUME_NAME: TypeAlias = Annotated[
    NonEmptyString,
    AfterValidator(
        match_validator(
            RE_VOLUME_NAME,
            'Name can contain only letters, numbers, dashes, underscores and dots. '
            'Name must start with a letter, and must not end with a dash.'
        ),
    ),
    StringConstraints(max_length=63),
]


class VirtVolumeEntry(BaseModel):
    id: NonEmptyString
    name: NonEmptyString
    storage_pool: NonEmptyString
    content_type: NonEmptyString
    created_at: str
    type: NonEmptyString
    config: dict
    used_by: list[NonEmptyString]


@single_argument_args('virt_volume_create')
class VirtVolumeCreateArgs(BaseModel):
    name: VOLUME_NAME
    content_type: Literal['BLOCK'] = 'BLOCK'
    size: int = Field(ge=512, default=1024)  # 1 gb default
    '''Size of volume in MB and it should at least be 512 MB'''
    storage_pool: NonEmptyString | None = None
    '''
    Storage pool in which to create the volume. This must be one of pools listed
    in virt.global.config output under `storage_pools`. If the value is None, then
    the pool defined as `pool` in virt.global.config will be used.
    '''


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
class VirtVolumeImportIsoArgs(BaseModel):
    name: VOLUME_NAME
    '''Specify name of the newly created volume from the ISO specified'''
    iso_location: NonEmptyString | None = None
    upload_iso: bool = False
    storage_pool: NonEmptyString | None = None
    '''
    Storage pool in which to create the volume. This must be one of pools listed
    in virt.global.config output under `storage_pools`. If the value is None, then
    the pool defined as `pool` in virt.global.config will be used.
    '''


class VirtVolumeImportIsoResult(BaseModel):
    result: VirtVolumeEntry


class ZvolImportEntry(BaseModel):
    virt_volume_name: VOLUME_NAME
    '''Specify name of the newly created volume from the ISO specified'''
    zvol_path: NonEmptyString
    '''Specify path of zvol in /dev/zvol'''

    @field_validator('zvol_path')
    @classmethod
    def validate_source(cls, zvol_path):
        if not zvol_path.startswith('/dev/zvol/'):
            raise ValueError('Not a valid /dev/zvol path')

        return zvol_path


@single_argument_args('virt_volume_import_iso')
class VirtVolumeImportZvolArgs(BaseModel):
    to_import: list[ZvolImportEntry]
    '''List of zvols to import as volumes'''
    clone: bool = False
    '''Optionally clone and promote zvol'''


class VirtVolumeImportZvolResult(BaseModel):
    result: VirtVolumeEntry
