from typing import Any

__all__ = (
    "RECORDSIZE_MAPPING",
    "ZFS_CHECKSUM_CHOICES",
    "ZFS_COMPRESSION_ALGORITHM_CHOICES",
    "recommended_zvol_blocksize",
    "recordsize_choices",
)

ZFS_CHECKSUM_CHOICES = ["ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3"]
ZFS_COMPRESSION_ALGORITHM_CHOICES = [
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
    "ZSTD-1",
    "ZSTD-2",
    "ZSTD-3",
    "ZSTD-4",
    "ZSTD-5",
    "ZSTD-6",
    "ZSTD-7",
    "ZSTD-8",
    "ZSTD-9",
    "ZSTD-10",
    "ZSTD-11",
    "ZSTD-12",
    "ZSTD-13",
    "ZSTD-14",
    "ZSTD-15",
    "ZSTD-16",
    "ZSTD-17",
    "ZSTD-18",
    "ZSTD-19",
    "ZSTD-FAST-1",
    "ZSTD-FAST-2",
    "ZSTD-FAST-3",
    "ZSTD-FAST-4",
    "ZSTD-FAST-5",
    "ZSTD-FAST-6",
    "ZSTD-FAST-7",
    "ZSTD-FAST-8",
    "ZSTD-FAST-9",
    "ZSTD-FAST-10",
    "ZSTD-FAST-20",
    "ZSTD-FAST-30",
    "ZSTD-FAST-40",
    "ZSTD-FAST-50",
    "ZSTD-FAST-60",
    "ZSTD-FAST-70",
    "ZSTD-FAST-80",
    "ZSTD-FAST-90",
    "ZSTD-FAST-100",
    "ZSTD-FAST-500",
    "ZSTD-FAST-1000",
]

# https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Module%20Parameters.html#zfs-max-recordsize
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
