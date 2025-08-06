from middlewared.utils import BOOT_POOL_NAME_VALID

INTERNAL_PATHS = (
    "ix-apps",
    ".ix-virt",
    "ix-applications",
    ".system"
) + tuple(BOOT_POOL_NAME_VALID)

__all__ = ("has_internal_path",)


def has_internal_path(path):
    """
    Check if the given path contains, is, or is under any internal system path.

    Args:
        path: A relative path string (e.g., 'tank/ix-apps/foo')

    Returns:
        bool: True if path has any internal component, False otherwise
    """
    return any(i in INTERNAL_PATHS for i in path.split("/"))
