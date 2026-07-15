from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from middlewared.plugins.initramfs import write_initramfs_flags
from middlewared.service import CallError
from middlewared.utils.boot.models import BootUpdateInitramfsOptions
from middlewared.utils.rootfs_protection import rootfs_protection_lock

if TYPE_CHECKING:
    from middlewared.main import Middleware


def rebuild_initramfs(force: bool) -> bool:
    """Rebuild the initramfs, returning ``True`` if it changed and ``False`` otherwise.

    Synchronous and blocking (subprocess + lock); async callers invoke the
    ``boot.update_initramfs`` method via ``call2`` so it runs in the io thread pool.
    """
    args = ["/"]
    if force:
        args.append("-f")

    # Hold the rootfs-protection lock across the rebuild so it can't race
    # disable-rootfs-protection (see middlewared.utils.rootfs_protection):
    # truenas-initrd.py transiently makes the rootfs writable and restores it.
    # NOTE: truenas-initrd.py is provided by truenas/upgrade_pyutils repository
    with rootfs_protection_lock():
        cp = subprocess.run(
            ["/usr/local/bin/truenas-initrd.py", *args],
            capture_output=True,
            encoding="utf8",
            errors="ignore",
        )
    if cp.returncode > 1:
        raise CallError(f"Failed to update initramfs: {cp.stdout} {cp.stderr}")

    return cp.returncode == 1


def on_config_upload(middleware: Middleware, path: str) -> None:
    # Materialize every /data/subsystems/initramfs/* flag from the *uploaded*
    # DB before the in-process datastore swap (which only happens at next
    # boot, in the config plugin's setup). Without this the regenerated initrd
    # reflects the OLD live DB, and the user has to reboot a second time
    # before the new config takes effect.
    #
    # Hook is synchronous (call_hook_sync) so we run on the calling thread,
    # do the file writes inline, and dispatch the rebuild back through the
    # event loop via call_sync2.
    write_initramfs_flags(middleware, path)
    middleware.call_sync2(middleware.services.boot.update_initramfs, BootUpdateInitramfsOptions(force=True))
