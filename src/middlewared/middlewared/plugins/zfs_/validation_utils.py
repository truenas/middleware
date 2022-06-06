import libzfs


def validate_pool_name(name: str) -> bool:
    return libzfs.validate_pool_name(name)


def validate_dataset_name(name: str) -> bool:
    return libzfs.validate_dataset_name(name)


def validate_snapshot_name(name: str) -> bool:
    return libzfs.validate_snapshot_name(name)
