from typing import Any

__all__ = (
    "RECORDSIZE_MAPPING",
    "recommended_zvol_blocksize",
    "recordsize_choices",
)

# https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Module%20Parameters.html#zfs-max-recordsize
RECORDSIZE_MAPPING = (
    (1 << 9, "512"),
    (1 << 9, "512B"),
    (1 << 10, "1K"),
    (1 << 11, "2K"),
    (1 << 12, "4K"),
    (1 << 13, "8K"),
    (1 << 14, "16K"),
    (1 << 15, "32K"),
    (1 << 16, "64K"),
    (1 << 17, "128K"),
    (1 << 18, "256K"),
    (1 << 19, "512K"),
    (1 << 20, "1M"),
    (1 << 21, "2M"),
    (1 << 22, "4M"),
    (1 << 23, "8M"),
    (1 << 24, "16M"),
)

DRAID_MINIMUM_RECORDSIZE = 1 << 17


def recordsize_choices(max_recordsize: int, draid: bool) -> list[str]:
    minimum_recordsize = DRAID_MINIMUM_RECORDSIZE if draid else RECORDSIZE_MAPPING[0][0]
    return [v for k, v in RECORDSIZE_MAPPING if minimum_recordsize <= k <= max_recordsize]


def recommended_zvol_blocksize(data_vdevs: list[dict[str, Any]]) -> str:
    """
    Cheatsheat for blocksizes is as follows:
    2w/3w mirror = 16K
    3wZ1, 4wZ2, 5wZ3 = 16K
    4w/5wZ1, 5w/6wZ2, 6w/7wZ3 = 32K
    6w/7w/8w/9wZ1, 7w/8w/9w/10wZ2, 8w/9w/10w/11wZ3 = 64K
    10w+Z1, 11w+Z2, 12w+Z3 = 128K
    """
    maxdisks = 1
    for vdev in data_vdevs:
        if vdev["vdev_type"] == "raidz1":
            disks = len(vdev["children"]) - 1
        elif vdev["vdev_type"] == "raidz2":
            disks = len(vdev["children"]) - 2
        elif vdev["vdev_type"] == "raidz3":
            disks = len(vdev["children"]) - 3
        elif vdev["vdev_type"] == "mirror":
            disks = maxdisks
        else:
            disks = len(vdev["children"])

        if disks > maxdisks:
            maxdisks = disks

    return f"{max(16, min(128, 2 ** ((maxdisks * 8) - 1).bit_length()))}K"
