from __future__ import annotations

import asyncio
import contextlib
import subprocess
from typing import TYPE_CHECKING, Any

from middlewared.service_exception import CallError
from middlewared.utils import run

if TYPE_CHECKING:
    from middlewared.api.current import TunableEntry
    from middlewared.main import Middleware


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


def set_sysctl(middleware: Middleware, var: str, value: str, ha_propagate: bool = False) -> None:
    path = f'/proc/sys/{var.replace(".", "/")}'
    with contextlib.suppress(FileNotFoundError, PermissionError):
        with open(path, 'w') as f:
            f.write(value)

    if ha_propagate:
        middleware.call_sync('failover.call_remote', 'tunable.set_sysctl', [var, value])


def reset_sysctl(middleware: Middleware, tunable: TunableEntry, ha_propagate: bool = False) -> None:
    set_sysctl(middleware, tunable.var, tunable.orig_value, ha_propagate)


def zfs_parameter_path(name: str) -> str:
    return f'/sys/module/zfs/parameters/{name}'


def zfs_parameter_value(name: str) -> str:
    with open(zfs_parameter_path(name)) as f:
        return f.read().strip()


def set_zfs_parameter(middleware: Middleware, name: str, value: str, ha_propagate: bool = False) -> None:
    path = zfs_parameter_path(name)
    with contextlib.suppress(FileNotFoundError, PermissionError):
        with open(path, 'w') as f:
            f.write(value)

    if ha_propagate:
        middleware.call_sync('failover.call_remote', 'tunable.set_zfs_parameter', [name, value])


def reset_zfs_parameter(middleware: Middleware, tunable: TunableEntry, ha_propagate: bool = False) -> None:
    set_zfs_parameter(middleware, tunable.var, tunable.orig_value, ha_propagate)


async def handle_tunable_change(middleware: Middleware, tunable: dict[str, Any], ha_propagate: bool = False) -> None:
    if tunable['type'] == 'UDEV':
        await middleware.call('etc.generate', 'udev')
        await run(['udevadm', 'control', '-R'])

        if ha_propagate:
            await middleware.call(
                'failover.call_remote', 'tunable.handle_tunable_change', [tunable],
            )


async def generate_sysctl(middleware: Middleware, ha_propagate: bool = False) -> None:
    await middleware.call('etc.generate', 'sysctl')
    if ha_propagate:
        await middleware.call('failover.call_remote', 'etc.generate', ['sysctl'])


async def update_initramfs(middleware: Middleware, ha_propagate: bool = False) -> None:
    if ha_propagate:
        tasks = [
            middleware.create_task(middleware.call('boot.update_initramfs')),
            middleware.call('failover.call_remote', 'boot.update_initramfs', [], {
                'timeout': 300,
            })
        ]

        errors = []
        for i, result in enumerate(await asyncio.gather(*tasks, return_exceptions=True)):
            if isinstance(result, Exception):
                if i == 0:
                    error = 'Failed to update initramfs on local node: '
                else:
                    error = 'Failed to update initramfs on remote node node: '

                errors.append(error + str(result))

        if errors:
            raise CallError('\n'.join(errors))
    else:
        await middleware.call('boot.update_initramfs')
