import enum

class TDBError(enum.IntEnum):
    SUCCESS = 0
    CORRUPT = enum.auto()
    IO = enum.auto()
    LOCK = enum.auto()
    OOM = enum.auto()
    EXISTS = enum.auto()
    NOLOCK = enum.auto()
    TIMEOUT = enum.auto()
    NOEXIST = enum.auto()
    EINVAL = enum.auto()
    RDONLY = enum.auto()
    NESTING = enum.auto()
