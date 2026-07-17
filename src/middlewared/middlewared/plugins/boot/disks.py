import os


def get_boot_type() -> str:
    """Return the boot type of the boot pool: ``EFI`` or ``BIOS``."""
    # https://wiki.debian.org/UEFI
    return "EFI" if os.path.exists("/sys/firmware/efi") else "BIOS"
