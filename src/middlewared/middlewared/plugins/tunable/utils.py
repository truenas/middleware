from __future__ import annotations

import contextlib
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.api.current import TunableEntry


TUNABLE_TYPES: list[str] = ['SYSCTL', 'UDEV', 'ZFS']

_SYSCTLS: set[str] = set()


def get_sysctls() -> set[str]:
    if not _SYSCTLS:
        result = subprocess.run(['sysctl', '-aN'], stdout=subprocess.PIPE)
        for line in result.stdout.decode().split('\n'):
            if line:
                _SYSCTLS.add(line)
    return _SYSCTLS


def get_sysctl(var: str) -> str:
    with open(f'/proc/sys/{var.replace(".", "/")}') as f:
        return f.read().strip()


def set_sysctl(var: str, value: str) -> None:
    path = f'/proc/sys/{var.replace(".", "/")}'
    with contextlib.suppress(FileNotFoundError, PermissionError):
        with open(path, 'w') as f:
            f.write(value)


def reset_sysctl(tunable: TunableEntry) -> None:
    set_sysctl(tunable.var, tunable.orig_value)


def zfs_parameter_path(name: str) -> str:
    return f'/sys/module/zfs/parameters/{name}'


def zfs_parameter_value(name: str) -> str:
    with open(zfs_parameter_path(name)) as f:
        return f.read().strip()


def set_zfs_parameter(name: str, value: str) -> None:
    path = zfs_parameter_path(name)
    with contextlib.suppress(FileNotFoundError, PermissionError):
        with open(path, 'w') as f:
            f.write(value)


def reset_zfs_parameter(tunable: TunableEntry) -> None:
    set_zfs_parameter(tunable.var, tunable.orig_value)
