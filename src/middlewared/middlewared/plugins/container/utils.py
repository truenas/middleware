import os
import subprocess

from truenas_os_pyutils.io import atomic_write

__all__ = (
    "CONTAINER_DS_NAME",
    "container_dataset",
    "container_dataset_mountpoint",
    "container_instance_dataset_mountpoint",
    "nsenter_set_hostname",
    "update_etc_hosts",
    "write_etc_hostname",
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


def write_etc_hostname(rootfs: str, name: str) -> None:
    with atomic_write(os.path.join(rootfs, 'etc/hostname'), 'w') as f:
        f.write(f'{name}\n')


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


def update_etc_hosts(rootfs: str, name: str) -> None:
    hosts_path = os.path.join(rootfs, 'etc/hosts')
    existing_lines = []
    if os.path.exists(hosts_path):
        with open(hosts_path) as f:
            existing_lines = f.readlines()

    with atomic_write(hosts_path, 'w') as f:
        f.writelines(build_etc_hosts_content(existing_lines, name))


def nsenter_set_hostname(pid: int, name: str) -> None:
    subprocess.run(
        ['/usr/bin/nsenter', '--target', str(pid), '--uts', '--', 'hostname', name],
        capture_output=True, check=True,
    )
