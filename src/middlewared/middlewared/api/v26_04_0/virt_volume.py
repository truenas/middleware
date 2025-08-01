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
    """Unique identifier for the virtualization volume."""
    name: NonEmptyString
    """Human-readable name of the virtualization volume."""
    storage_pool: NonEmptyString
    """Name of the storage pool containing this volume."""
    content_type: NonEmptyString
    """Type of content stored in this volume (e.g., 'BLOCK', 'ISO')."""
    created_at: str
    """Timestamp when this volume was created."""
    type: NonEmptyString
    """Volume type indicating its storage backend and characteristics."""
    config: dict
    """Object containing detailed configuration parameters for this volume."""
    used_by: list[NonEmptyString]
    """Array of virtual instance names currently using this volume."""


@single_argument_args('virt_volume_create')
class VirtVolumeCreateArgs(BaseModel):
    name: VOLUME_NAME
    """Name for the new virtualization volume (alphanumeric, dashes, dots, underscores)."""
    content_type: Literal['BLOCK'] = 'BLOCK'
    size: int = Field(ge=512, default=1024)  # 1 gb default
    """Size of volume in MB and it should at least be 512 MB."""
    storage_pool: NonEmptyString | None = None
    """
    Storage pool in which to create the volume. This must be one of pools listed \
    in virt.global.config output under `storage_pools`. If the value is None, then \
    the pool defined as `pool` in virt.global.config will be used.
    """


class VirtVolumeCreateResult(BaseModel):
    result: VirtVolumeEntry
    """The newly created virtualization volume configuration."""


class VirtVolumeUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    size: int = Field(ge=512)
    """New size for the volume in MB (minimum 512MB)."""


class VirtVolumeUpdateArgs(BaseModel):
    id: NonEmptyString
    """Identifier of the virtualization volume to update."""
    virt_volume_update: VirtVolumeUpdate
    """Updated configuration for the virtualization volume."""


class VirtVolumeUpdateResult(BaseModel):
    result: VirtVolumeEntry
    """The updated virtualization volume configuration."""


class VirtVolumeDeleteArgs(BaseModel):
    id: NonEmptyString
    """Identifier of the virtualization volume to delete."""


class VirtVolumeDeleteResult(BaseModel):
    result: Literal[True]
    """Always returns true on successful volume deletion."""


@single_argument_args('virt_volume_import_iso')
class VirtVolumeImportIsoArgs(BaseModel):
    name: VOLUME_NAME
    """Specify name of the newly created volume from the ISO specified."""
    iso_location: NonEmptyString | None = None
    """Path to the ISO file to import. `null` if uploading via `upload_iso`."""
    upload_iso: bool = False
    """Whether to upload an ISO file instead of using a local file path."""
    storage_pool: NonEmptyString | None = None
    """
    Storage pool in which to create the volume. This must be one of pools listed \
    in virt.global.config output under `storage_pools`. If the value is None, then \
    the pool defined as `pool` in virt.global.config will be used.
    """


class VirtVolumeImportIsoResult(BaseModel):
    result: VirtVolumeEntry
    """The newly created volume from the imported ISO file."""


class ZvolImportEntry(BaseModel):
    virt_volume_name: VOLUME_NAME
    """Name for the new virtualization volume created from the imported ZFS volume."""
    zvol_path: NonEmptyString
    """Full path to the ZFS volume device in /dev/zvol/."""

    @field_validator('zvol_path')
    @classmethod
    def validate_source(cls, zvol_path):
        if not zvol_path.startswith('/dev/zvol/'):
            raise ValueError('Not a valid /dev/zvol path')

        return zvol_path


@single_argument_args('virt_volume_import_iso')
class VirtVolumeImportZvolArgs(BaseModel):
    to_import: list[ZvolImportEntry]
    """Array of ZFS volumes to import as virtualization volumes."""
    clone: bool = False
    """Whether to clone and promote the ZFS volume instead of importing directly."""


class VirtVolumeImportZvolResult(BaseModel):
    result: VirtVolumeEntry
    """The newly created volume from the imported ZFS volume."""
