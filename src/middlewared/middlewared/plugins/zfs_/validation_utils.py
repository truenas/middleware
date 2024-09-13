import libzfs

from .utils import zvol_name_to_path


def check_zvol_in_boot_pool_using_name(zvol_name: str) -> bool:
    return check_zvol_in_boot_pool_using_path(zvol_name_to_path(zvol_name))


def check_zvol_in_boot_pool_using_path(zvol_path: str) -> bool:
    from middlewared.plugins.boot import BOOT_POOL_NAME
    return zvol_path.startswith(f'/dev/zvol/{BOOT_POOL_NAME}/')


def validate_pool_name(name: str) -> bool:
    return libzfs.validate_pool_name(name)


def validate_dataset_name(name: str) -> bool:
    return libzfs.validate_dataset_name(name)


def validate_snapshot_name(name: str) -> bool:
    return libzfs.validate_snapshot_name(name)
