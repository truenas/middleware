from dataclasses import dataclass
from typing import Literal

from middlewared.utils import BOOT_POOL_NAME_VALID

__all__ = (
    "get_encryption_info",
    "has_internal_path",
)


INTERNAL_PATHS = (
    "ix-apps",
    ".ix-virt",
    "ix-applications",
    ".system"
)


@dataclass(slots=True, frozen=True, kw_only=True)
class EncryptionInfo:
    encrypted: bool = False
    """Whether the zfs resource is encrypted"""
    encryption_type: Literal[None, "raw", "hex", "passphrase"] = None
    """Controls what format the user's encryption key will be provided as.
    NOTE: This property is only set when the dataset is encrypted."""
    locked: bool = False
    """Whether the zfs resource is locked"""
    location: str | None = None
    """Controls where the user's encryption key will be loaded from
    by default for commands such as zfs load-key and zfs mount -l.
    This property is only set for encrypted datasets which are
    encryption roots. If unspecified, the default is prompt.
    """


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


def get_encryption_info(data: dict) -> EncryptionInfo:
    """
    Check the various zfs properties to determine if the underlying zfs
    resource is encrypted.

    Args:
        data: dict with, minimally, the following keys to be able to
            accurately determine encryption status
            ('keystatus', 'encryption', 'keyformat', 'keylocation')

    Returns:
        dict: of keys representing the current encryption info and
            status
    """
    enc = data["encryption"]["raw"] != "off"
    if not enc:
        # no reason to continue
        return EncryptionInfo(encrypted=enc)
    else:
        return EncryptionInfo(
            encrypted=enc,
            encryption_type=data["keyformat"]["raw"],
            locked=data["keystatus"]["raw"] != "available",
            location=data["keylocation"]["raw"],
        )
