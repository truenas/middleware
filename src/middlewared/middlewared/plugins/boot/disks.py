from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from middlewared.utils import run
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID, get_boot_pool_name, set_boot_pool_name

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

# The boot-pool disk membership is cached module-level state, populated on first use. The boot-pool
# name itself lives in `middlewared.utils.boot.pool` so consumers outside this package can read it
# without importing the plugin's heavy package `__init__`.
_boot_pool_disks: tuple[str, ...] | None = None


def clear_disks_cache() -> None:
    """Clear the boot pool disk cache."""
    global _boot_pool_disks
    _boot_pool_disks = None


async def get_disks_cache(context: ServiceContext) -> list[str]:
    """Return the boot pool disks, populating the cache on first use.

    We cache this since it changes rarely and has many callers (especially on HA). An
    immutable tuple is stored because the value is globally cached.
    """
    global _boot_pool_disks
    if _boot_pool_disks is None:
        status = await context.middleware.call("zpool.status", {"name": get_boot_pool_name(), "real_paths": True})
        _boot_pool_disks = tuple(status["disks"])
    return list(_boot_pool_disks)


def get_boot_type() -> str:
    """Return the boot type of the boot pool: ``EFI`` or ``BIOS``."""
    # https://wiki.debian.org/UEFI
    return "EFI" if os.path.exists("/sys/firmware/efi") else "BIOS"


async def get_state_dict(context: ServiceContext) -> dict[str, Any]:
    """Raw boot-pool state (same structure as ``pool.pool_extend``) for internal callers.

    The public ``boot.get_state`` wraps this in a :class:`BootGetState` model; internal
    callers that index the result use this dict form directly.
    """
    info: dict[str, Any] = await context.middleware.call("pool.pool_normalize_info", get_boot_pool_name())
    return info


async def detect_boot_pool(context: ServiceContext) -> None:
    """Detect the boot pool name, prime the disk cache, and ensure grub2 compatibility.

    Run once from the plugin's ``setup()``; leaves the boot pool name unset (and logs) if no
    known boot pool is imported.
    """
    try:
        pools = dict(
            [
                line.split("\t")
                for line in (await run("zpool", "list", "-H", "-o", "name,compatibility", encoding="utf8"))
                .stdout.strip()
                .splitlines()
            ]
        )
    except Exception:
        # this isn't fatal, but we need to log something so we can review and fix as needed
        context.logger.warning("Unexpected failure parsing compatibility feature", exc_info=True)
        return

    for name in BOOT_POOL_NAME_VALID:
        if name in pools:
            set_boot_pool_name(name)
            await get_disks_cache(context)  # populates disk cache
            compatibility = pools[name]
            if compatibility != "grub2":
                context.logger.info("Boot pool %r has compatibility=%r, setting it to grub2", name, compatibility)
                try:
                    await run("zpool", "set", "compatibility=grub2", name)
                except Exception as e:
                    context.logger.error("Error setting boot pool compatibility: %r", e)
            break
    else:
        context.logger.error("Failed to detect boot pool name.")
