BOOT_POOL_NAME_VALID = ["freenas-boot", "boot-pool"]

# The detected boot-pool name is process-global state, populated by the boot plugin's `setup()`
# and read by many other plugins (and by pure, sync helpers that have no middleware handle). It is
# exposed ONLY through the accessor functions below — never import the raw name. Importing the
# mutable value directly binds a stale snapshot at import time (which happens before `setup()`
# runs), so a direct importer would permanently read `None`.
_boot_pool_name: str | None = None


def get_boot_pool_name() -> str | None:
    """Return the detected boot pool name (e.g. ``boot-pool``), or ``None`` before detection."""
    return _boot_pool_name


def set_boot_pool_name(name: str | None) -> None:
    global _boot_pool_name
    _boot_pool_name = name
