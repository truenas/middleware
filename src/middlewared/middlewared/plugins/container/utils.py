def container_dataset(pool: str) -> str:
    return f'{pool}/.truenas_containers'


def container_dataset_mountpoint(pool: str) -> str:
    return f'/.truenas_containers/{pool}'
