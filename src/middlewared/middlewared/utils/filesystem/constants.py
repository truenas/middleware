import enum

AT_FDCWD = -100  # special fd value meaning current working directory


class FileType(enum.Enum):
    DIRECTORY = enum.auto()
    FILE = enum.auto()
    SYMLINK = enum.auto()
    OTHER = enum.auto()


class ZFSCTL(enum.IntEnum):
    # from include/os/linux/zfs/sys/zfs_ctldir.h in ZFS repo
    INO_ROOT = 0x0000FFFFFFFFFFFF
    INO_SNAPDIR = 0x0000FFFFFFFFFFFD
