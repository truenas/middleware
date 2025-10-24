__all__ = (
    "CONTAINER_DS_NAME",
    "container_dataset",
    "container_dataset_mountpoint",
)

CONTAINER_DS_NAME = ".truenas_containers"


def container_dataset(pool: str) -> str:
    return f"{pool}/{CONTAINER_DS_NAME}"


def container_dataset_mountpoint(pool: str) -> str:
    return f"/{CONTAINER_DS_NAME}/{pool}"
