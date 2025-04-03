from typing import Literal

from middlewared.api.base import BaseModel, NonEmptyString, single_argument_args

from .virt_instance import VirtInstanceEntry
from .virt_volume import VirtVolumeEntry


__all__ = [
    'VirtBackupExportArgs', 'VirtBackupExportResult', 'VirtBackupImportArgs', 'VirtBackupImportResult',
]


@single_argument_args('virt_export_backup')
class VirtBackupExportArgs(BaseModel):
    backup_name: NonEmptyString
    resource_name: NonEmptyString
    resource_type: Literal['INSTANCE', 'VOLUME'] = 'INSTANCE'
    backup_instance_volumes: bool = False
    '''
    When resource specified to be backed up is an instance, only the root disk of the instance and
    it's configuration is backed up by default. If this flag is set, then all disks which are incus
    volumes and attached to the instance will be backed up as well.
    '''


class VirtBackupExportResult(BaseModel):
    result: str


@single_argument_args('virt_import_backup')
class VirtBackupImportArgs(BaseModel):
    resource_name: NonEmptyString
    resource_type: Literal['INSTANCE', 'VOLUME'] = 'INSTANCE'
    backup_location: NonEmptyString
    storage_pool: NonEmptyString | None = None


class VirtBackupImportResult(BaseModel):
    result: VirtInstanceEntry | VirtVolumeEntry
