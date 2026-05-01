from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
from typing import TYPE_CHECKING, Any

from truenas_os_pyutils.io import atomic_write

from middlewared.service_exception import CallError
from middlewared.utils import run

if TYPE_CHECKING:
    from middlewared.api.current import TunableEntry
    from middlewared.main import Middleware


TUNABLE_TYPES: list[str] = ['SYSCTL', 'UDEV', 'ZFS']

# Lives under /data so it persists across BE upgrades (the installer rsyncs
# /data into the new BE). The initramfs hook copies this file into the initrd
# as /etc/modprobe.d/zfs.conf so options apply when zfs loads in the initramfs.
ZFS_MODPROBE_PATH = '/data/subsystems/initramfs/truenas_zfs_modprobe.conf'

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


def write_zfs_modprobe(middleware: Middleware) -> bool:
    """
    Materialize the zfs modprobe options from the enabled ZFS tunables to a
    stable path under /data. The initramfs-tools hook
    /etc/initramfs-tools/hooks/truenas_zfs_modprobe copies this file into the
    initrd as /etc/modprobe.d/zfs.conf so the options apply when zfs loads
    inside the initramfs (boot pool import).

    Returns True if the file changed (caller should force an initramfs rebuild).
    """
    options = []
    for tunable in middleware.call_sync(
        'tunable.query', [['type', '=', 'ZFS'], ['enabled', '=', True]]
    ):
        options.append(f'{tunable["var"]}={tunable["value"]}')

    # Sort so plain text equality is meaningful for change detection,
    # regardless of tunable.query / sysfs enumeration order.
    new_content = f'options zfs {" ".join(sorted(options))}\n' if options else ''

    try:
        with open(ZFS_MODPROBE_PATH) as f:
            existing_content = f.read()
    except FileNotFoundError:
        existing_content = ''

    if existing_content == new_content:
        return False

    os.makedirs(os.path.dirname(ZFS_MODPROBE_PATH), exist_ok=True)
    with atomic_write(ZFS_MODPROBE_PATH, 'w') as f:
        f.write(new_content)
    return True


async def update_initramfs(middleware: Middleware, ha_propagate: bool = False) -> None:
    if not ha_propagate:
        changed = await middleware.call('tunable.write_zfs_modprobe')
        await middleware.call('boot.update_initramfs', {'force': changed})
        return

    # Phase 1: write the modprobe config on both nodes. Must finish on both
    # before phase 2 — boot.update_initramfs runs the initramfs hook that
    # reads the file we just wrote.
    local_changed, remote_changed = await asyncio.gather(
        middleware.call('tunable.write_zfs_modprobe'),
        middleware.call('failover.call_remote', 'tunable.write_zfs_modprobe'),
    )

    # Phase 2: rebuild the initramfs on both nodes concurrently.
    results = await asyncio.gather(
        middleware.call('boot.update_initramfs', {'force': local_changed}),
        middleware.call(
            'failover.call_remote', 'boot.update_initramfs',
            [{'force': remote_changed}], {'timeout': 300},
        ),
        return_exceptions=True,
    )
    errors = []
    for node, result in zip(('local', 'remote'), results):
        if isinstance(result, Exception):
            errors.append(f'Failed to update initramfs on {node} node: {result}')
    if errors:
        raise CallError('\n'.join(errors))
