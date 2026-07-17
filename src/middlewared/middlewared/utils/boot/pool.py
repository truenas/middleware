from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from middlewared.utils import run

if TYPE_CHECKING:
    from middlewared.main import Middleware

logger = logging.getLogger(__name__)

BOOT_POOL_NAME_VALID = ["freenas-boot", "boot-pool"]


class BootPoolNotDetected(Exception):
    """Raised when the boot pool name is requested before detection completed."""


class BootPoolState:
    """Process-global boot-pool identity and disk membership.

    Populated by the boot plugin's ``setup()`` (via ``initialize``) and read by many other
    plugins, including pure sync helpers that have no middleware handle. Consumers must go
    through the accessors below — never bind the internal attributes at import time (which
    happens before detection runs). The ``middleware`` handle is only ever a parameter (never
    imported), so this module stays free of heavy middleware/pydantic imports and remains cheap
    for its low-level consumers to import.
    """

    def __init__(self) -> None:
        self._name: str | None = None
        self._disks: tuple[str, ...] | None = None

    def get_name(self) -> str:
        """Return the detected boot pool name (e.g. ``boot-pool``).

        Raises :class:`BootPoolNotDetected` if called before detection has run; the name is
        guaranteed present once middleware has started (a missing boot pool aborts startup).
        """
        if self._name is None:
            raise BootPoolNotDetected("Boot pool name requested before detection completed")
        return self._name

    def set_name(self, name: str) -> None:
        self._name = name

    async def get_disks(self, middleware: Middleware, use_cache: bool = True) -> list[str]:
        """Return the boot pool disks, populating the cache on first use.

        Cached because it changes rarely and has many callers (especially on HA); an immutable
        tuple is stored because the value is globally cached. Pass ``use_cache=False`` to
        re-derive the membership live from ``zpool.status`` and refill the cache (used to
        invalidate after the boot pool changes).
        """
        if not use_cache or self._disks is None:
            status = await middleware.call("zpool.status", {"name": self.get_name(), "real_paths": True})
            self._disks = tuple(status["disks"])
        return list(self._disks)

    async def initialize(self, middleware: Middleware) -> None:
        """Detect the boot pool, fill the disk cache, and ensure grub2 compatibility.

        Run once from the plugin's ``setup()``. Raises :class:`BootPoolNotDetected` (aborting
        middleware startup) if no known boot pool is imported — every downstream subsystem
        depends on it.
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
            # A transient failure parsing `zpool list` output is not proof the boot pool is
            # absent, so log and continue rather than aborting startup.
            logger.warning("Unexpected failure parsing compatibility feature", exc_info=True)
            return

        for name in BOOT_POOL_NAME_VALID:
            if name in pools:
                self.set_name(name)
                await self.get_disks(middleware)
                compatibility = pools[name]
                if compatibility != "grub2":
                    logger.info("Boot pool %r has compatibility=%r, setting it to grub2", name, compatibility)
                    try:
                        await run("zpool", "set", "compatibility=grub2", name)
                    except Exception as e:
                        logger.error("Error setting boot pool compatibility: %r", e)
                break
        else:
            raise BootPoolNotDetected("Failed to detect boot pool; no known boot pool is imported")


boot_pool = BootPoolState()
