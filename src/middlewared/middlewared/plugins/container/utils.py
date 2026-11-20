import os
import stat

import truenas_os
from truenas_os_pyutils.io import atomic_write

__all__ = (
    "CONTAINER_DS_NAME",
    "configure_hostname",
    "container_dataset",
    "container_dataset_mountpoint",
    "container_instance_dataset_mountpoint",
)

CONTAINER_DS_NAME = ".truenas_containers"
MAX_ETC_HOSTS_SIZE = 1024 * 1024


def container_dataset(pool: str) -> str:
    """Returns the ZFS filesystem path for containers in `pool`."""
    return f"{pool}/{CONTAINER_DS_NAME}"


def container_dataset_mountpoint(pool: str) -> str:
    """Returns the mount point for the container filesystem."""
    return f"/{CONTAINER_DS_NAME}/{pool}"


def container_instance_dataset_mountpoint(pool: str, container_name: str) -> str:
    """Returns the mount point for a specific container."""
    return f"{container_dataset_mountpoint(pool)}/containers/{container_name}"


def build_etc_hosts_content(existing_lines: list[str], name: str) -> list[str]:
    lines = []
    found = False
    for line in existing_lines:
        parts = line.split()
        if parts and parts[0] == '127.0.1.1':
            lines.append(f'127.0.1.1\t{name}\n')
            found = True
        else:
            lines.append(line)

    if not found:
        lines.append(f'127.0.1.1\t{name}\n')

    return lines


def _read_etc_hosts(root_fd: int) -> list[str]:
    # The container controls its rootfs: resolve symlinks as the container would, never outside it
    try:
        fd = truenas_os.openat2(
            'etc/hosts', flags=os.O_RDONLY | os.O_NONBLOCK, dir_fd=root_fd,
            resolve=truenas_os.RESOLVE_IN_ROOT | truenas_os.RESOLVE_NO_MAGICLINKS,
        )
    except FileNotFoundError:
        return []

    with os.fdopen(fd) as f:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_ETC_HOSTS_SIZE:
            # FIFO, device or oversized file: start from an empty one
            return []
        return f.readlines()


def configure_hostname(rootfs: str, name: str) -> None:
    """Write the container's /etc/hostname and set its 127.0.1.1 line in /etc/hosts."""
    root_fd = os.open(rootfs, os.O_PATH | os.O_DIRECTORY)
    try:
        existing_lines = _read_etc_hosts(root_fd)
    finally:
        os.close(root_fd)

    # atomic_write refuses a symlink anywhere in the path before creating anything
    with atomic_write(os.path.join(rootfs, 'etc/hostname'), 'w') as f:
        f.write(f'{name}\n')
    with atomic_write(os.path.join(rootfs, 'etc/hosts'), 'w') as f:
        f.writelines(build_etc_hosts_content(existing_lines, name))
