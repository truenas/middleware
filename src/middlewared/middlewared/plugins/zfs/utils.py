from middlewared.utils import BOOT_POOL_NAME_VALID

__all__ = ("has_internal_path",)


INTERNAL_PATHS = (
    "ix-apps",
    ".ix-virt",
    "ix-applications",
    ".system"
)


def has_internal_path(path):
    """
    Check if a ZFS resource path is an internal path.

    Internal paths include:
    - Boot pools themselves ('boot-pool', 'freenas-boot') and any dataset under them
    - System datasets directly under a data pool (e.g., 'tank/ix-apps', 'tank/.system')

    Args:
        path: A ZFS resource relative path string (e.g., 'tank/ix-apps/foo', 'boot-pool/grub')

    Returns:
        bool: True if the path represents an internal path, False otherwise
    """
    components = path.split("/")
    if components[0] in BOOT_POOL_NAME_VALID:
        return True
    return len(components) > 1 and components[1] in INTERNAL_PATHS
