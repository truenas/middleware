from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString, single_argument_args

from .pool_dataset import ZFS_MAX_DATASET_NAME_LEN


__all__ = ['VirtInstanceStorageRenameArgs', 'VirtInstanceStorageRenameResult']


@single_argument_args('virt_instance_storage_rename')
class VirtInstanceStorageRenameArgs(BaseModel):
    name: NonEmptyString
    new_name: NonEmptyString = Field(..., max_length=ZFS_MAX_DATASET_NAME_LEN)


class VirtInstanceStorageRenameResult(BaseModel):
    result: bool
