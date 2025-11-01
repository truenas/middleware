__all__ = (
    "CONTAINER_DS_NAME",
    "container_dataset",
    "container_dataset_mountpoint",
    "container_instance_dataset_mountpoint",
)

CONTAINER_DS_NAME = ".truenas_containers"


def container_dataset(pool: str) -> str:
    """Returns the ZFS filesystem path for containers in `pool`."""
    return f"{pool}/{CONTAINER_DS_NAME}"


def container_dataset_mountpoint(pool: str) -> str:
    """Returns the mount point for the container filesystem."""
    return f"/{CONTAINER_DS_NAME}/{pool}"


def container_instance_dataset_mountpoint(pool: str, container_name: str) -> str:
    """Returns the mount point for a specific container."""
    return f"{container_dataset_mountpoint(pool)}/containers/{container_name}"
