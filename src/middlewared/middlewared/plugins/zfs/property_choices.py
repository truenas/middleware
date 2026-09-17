import itertools
from typing import Any

__all__ = (
    "RECORDSIZE_MAPPING",
    "ZFS_CHECKSUM_CHOICES",
    "ZFS_COMPRESSION_ALGORITHM_CHOICES",
    "recommended_zvol_blocksize",
    "recordsize_choices",
)

ZFS_CHECKSUM_CHOICES = ["ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3"]
ZFS_COMPRESSION_ALGORITHM_CHOICES = (
    [
        "ON",
        "OFF",
        "LZ4",
        "GZIP",
        "GZIP-1",
        "GZIP-9",
        "ZSTD",
        "ZSTD-FAST",
        "ZLE",
        "LZJB",
    ]
    + [f"ZSTD-{i}" for i in range(1, 20)]
    + [f"ZSTD-FAST-{i}" for i in itertools.chain(range(1, 11), range(20, 110, 10), range(500, 1500, 500))]
)

# https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Module%20Parameters.html#zfs-max-recordsize
# Maximum supported (at time of writing) is 16MB.
RECORDSIZE_MAPPING = [
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
]

DRAID_MINIMUM_RECORDSIZE = 1 << 17


def recordsize_choices(max_recordsize: int, draid: bool) -> list[str]:
    """Record sizes a filesystem may be given, between the pool's minimum and `max_recordsize`."""
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

    If the zpool was forcefully created with mismatched
    vdev geometry (i.e. 3wZ1 and a 5wZ1) then we calculate
    the blocksize based on the largest vdev of the zpool.
    """
    maxdisks = 1
    for vdev in data_vdevs:
        if vdev["type"] == "RAIDZ1":
            disks = len(vdev["children"]) - 1
        elif vdev["type"] == "RAIDZ2":
            disks = len(vdev["children"]) - 2
        elif vdev["type"] == "RAIDZ3":
            disks = len(vdev["children"]) - 3
        elif vdev["type"] == "MIRROR":
            disks = maxdisks
        else:
            disks = len(vdev["children"])

        if disks > maxdisks:
            maxdisks = disks

    return f"{max(16, min(128, 2 ** ((maxdisks * 8) - 1).bit_length()))}K"
