from middlewared.api.base import BaseModel, NonEmptyString, single_argument_args


__all__ = ['VirtBackupStoragePoolArgs', 'VirtBackupStoragePoolResult']


@single_argument_args('virt_backup_storage_pool')
class VirtBackupStoragePoolArgs(BaseModel):
    incus_storage_pool: NonEmptyString
    target_pool: NonEmptyString


class VirtBackupStoragePoolResult(BaseModel):
    result: bool
