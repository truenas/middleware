"""
Single source of truth for the TrueNAS-specific files baked into the initrd.

`truenas-initrd.py` and the per-feature initramfs-tools hooks shipped by the
`truenas-files` package read these paths at update-initramfs time. Each one
is materialized from configuration the user controls via middleware.

`write_initramfs_flags` is the only function that writes any of them. It is
called from:
  - the per-feature change paths (system.advanced.update for debugkernel,
    update_gpu_pci_ids for vfio, tunable CRUD for zfs modprobe)
  - on_config_upload, with the uploaded sqlite path so the new initrd reflects
    the uploaded values before the post-reboot datastore swap
  - the system.ready reconciliation handler, as defense-in-depth against drift
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from typing import TYPE_CHECKING

from truenas_os_pyutils.io import atomic_write
from truenas_pylibvirt.utils.gpu import get_gpus

if TYPE_CHECKING:
    from middlewared.main import Middleware


BASE = "/data/subsystems/initramfs"
DEBUG_KERNEL_FLAG_PATH = f"{BASE}/debug_kernel"
ZFS_MODPROBE_PATH = f"{BASE}/truenas_zfs_modprobe.conf"
VFIO_PCI_IDS_PATH = f"{BASE}/truenas_vfio_pci_ids"


def _atomic_replace_if_changed(path: str, content: str) -> bool:
    try:
        with open(path) as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""
    if existing == content:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with atomic_write(path, "w") as f:
        f.write(content)
    return True


def _read_from_sqlite(db_path: str) -> tuple[bool, list, list[tuple[str, str]]]:
    # Read directly from a sqlite path that isn't the live datastore. Used by
    # config-upload hooks where running middleware's SQLAlchemy engine is
    # still bound to the old DB file (the swap to the uploaded one happens
    # at next boot in the config plugin's setup). Read-only URI so we never
    # mutate the source.
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        adv = conn.execute("SELECT adv_debugkernel, adv_isolated_gpu_pci_ids FROM system_advanced LIMIT 1").fetchone()
        zfs = conn.execute(
            "SELECT tun_var, tun_value FROM system_tunable WHERE tun_type = 'ZFS' AND tun_enabled = 1"
        ).fetchall()
    debugkernel = bool(adv and adv[0])
    igpi = json.loads(adv[1]) if adv and adv[1] else []
    return debugkernel, igpi, zfs


def _read_from_middleware(middleware: Middleware) -> tuple[bool, list, list[tuple[str, str]]]:
    cfg = middleware.call_sync("system.advanced.config")
    debugkernel = cfg["debugkernel"]
    igpi = cfg.get("isolated_gpu_pci_ids") or []
    zfs = [
        (t.var, t.value)
        for t in middleware.call_sync2(
            middleware.services.tunable.query,
            [["type", "=", "ZFS"], ["enabled", "=", True]],
        )
    ]
    return debugkernel, igpi, zfs


def _expand_vfio_slots(igpi: list[str]) -> list[str]:
    # A "GPU" is actually a group of PCI functions sharing an IOMMU group
    # (video + HDMI audio + sometimes a USB-C controller). All siblings must
    # be bound to vfio-pci together, passthrough fails otherwise. So flatten
    # gpu['devices'] into the slot list.
    #
    # Skip the live PCI scan entirely when no GPUs are isolated, since
    # get_gpus() walks /sys and isn't free.
    if not igpi:
        return []
    slots = []
    for gpu in get_gpus():
        if gpu["addr"]["pci_slot"] in igpi:
            for dev in gpu["devices"]:
                slots.append(dev["pci_slot"])
    return slots


def write_initramfs_flags(middleware: Middleware, db_path: str | None = None) -> bool:
    """
    Read all initramfs-relevant config in a single pass and materialize every
    flag file under /data/subsystems/initramfs/. Returns True if any file
    changed (caller should force an initramfs rebuild).

    When `db_path` is None, reads from the live datastore. When provided,
    reads directly from the sqlite file at that path so callers (e.g.
    config-upload hooks) can run before the in-process datastore swap.

    Sync. Call from a thread (`asyncio.to_thread`) when invoked from a
    coroutine.
    """
    if db_path is not None:
        debugkernel, igpi, zfs_tunables = _read_from_sqlite(db_path)
    else:
        debugkernel, igpi, zfs_tunables = _read_from_middleware(middleware)

    debug_content = "1\n" if debugkernel else "0\n"
    zfs_content = f"options zfs {' '.join(sorted(f'{k}={v}' for k, v in zfs_tunables))}\n" if zfs_tunables else ""
    vfio_content = "".join(f"{s}\n" for s in sorted(_expand_vfio_slots(igpi)))

    changed = False
    if _atomic_replace_if_changed(DEBUG_KERNEL_FLAG_PATH, debug_content):
        changed = True
    if _atomic_replace_if_changed(ZFS_MODPROBE_PATH, zfs_content):
        changed = True
    if _atomic_replace_if_changed(VFIO_PCI_IDS_PATH, vfio_content):
        changed = True
    return changed


async def _event_system_ready(middleware, event_type, args):
    # Don't block boot
    middleware.create_task(_reconcile(middleware))


async def _reconcile(middleware):
    try:
        # GPU validation may mutate the DB (removes invalid PCI IDs and emits
        # alerts), so run it before materializing flags so the writes pick up
        # the cleaned state.
        await middleware.call("system.advanced.validate_isolated_gpus_on_boot")
        changed = await asyncio.to_thread(write_initramfs_flags, middleware)
        if changed:
            await middleware.call("boot.update_initramfs", {"force": True})
    except Exception:
        middleware.logger.error("Failed to reconcile initramfs flags", exc_info=True)


async def setup(middleware):
    middleware.event_subscribe("system.ready", _event_system_ready)
