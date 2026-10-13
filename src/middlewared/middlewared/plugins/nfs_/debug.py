from contextlib import suppress
import enum
import os
from typing import Literal

from middlewared.api.base import BaseModel, UniqueList

SUNRPC_DIR = "/proc/sys/sunrpc"


class NFS_DBGFLAGS(enum.Enum):
    # include/uapi/linux/nfs_fs.h
    NONE = 0x0000
    VFS = 0x0001
    DIRCACHE = 0x0002
    LOOKUPCACHE = 0x0004
    PAGECACHE = 0x0008
    PROC = 0x0010
    XDR = 0x0020
    FILE = 0x0040
    ROOT = 0x0080
    CALLBACK = 0x0100
    CLIENT = 0x0200
    MOUNT = 0x0400
    FSCACHE = 0x0800
    PNFS = 0x1000
    PNFS_LD = 0x2000
    STATE = 0x4000
    XATTR_CACHE = 0x8000
    ALL = 0xFFFF


class NFSD_DBGFLAGS(enum.Enum):
    # include/uapi/linux/nfsd/debug.h
    NONE = 0x0000
    SOCK = 0x0001
    FH = 0x0002
    EXPORT = 0x0004
    SVC = 0x0008
    PROC = 0x0010
    FILEOP = 0x0020
    AUTH = 0x0040
    REPCACHE = 0x0080
    XDR = 0x0100
    LOCKD = 0x0200
    PNFS = 0x0400
    ALL = 0x7FFF
    # NOCHANGE        0xFFFF


class NLM_DBGFLAGS(enum.Enum):
    # include/linux/lockd/debug.h
    NONE = 0x0000
    SVC = 0x0001
    CLIENT = 0x0002
    CLNTLOCK = 0x0004
    SVCLOCK = 0x0008
    MONITOR = 0x0010
    CLNTSUBS = 0x0020
    SVCSUBS = 0x0040
    HOSTCACHE = 0x0080
    XDR = 0x0100
    ALL = 0x7FFF


class RPC_DBGFLAGS(enum.Enum):
    # include/uapi/linux/sunrpc/debug.h
    NONE = 0x0000
    XPRT = 0x0001
    CALL = 0x0002
    DEBUG = 0x0004
    NFS = 0x0008
    AUTH = 0x0010
    BIND = 0x0020
    SCHED = 0x0040
    TRANS = 0x0080
    SVCXPRT = 0x0100
    SVCDSP = 0x0200
    MISC = 0x0400
    CACHE = 0x0800
    ALL = 0x7FFF


DebugFlags = type[NFS_DBGFLAGS] | type[NFSD_DBGFLAGS] | type[NLM_DBGFLAGS] | type[RPC_DBGFLAGS]

DBGCLS: dict[str, DebugFlags] = {
    "NFS": NFS_DBGFLAGS,
    "NFSD": NFSD_DBGFLAGS,
    "NLM": NLM_DBGFLAGS,
    "RPC": RPC_DBGFLAGS,
}


class NfsDebug(BaseModel):
    """Debug flags per RPC service. On input `null` leaves that service alone; on output it means
    the service has no entry in /proc/sys/sunrpc."""

    NFS: UniqueList[Literal[*NFS_DBGFLAGS.__members__]] | None = None  # type: ignore[valid-type]
    NFSD: UniqueList[Literal[*NFSD_DBGFLAGS.__members__]] | None = None  # type: ignore[valid-type]
    NLM: UniqueList[Literal[*NLM_DBGFLAGS.__members__]] | None = None  # type: ignore[valid-type]
    RPC: UniqueList[Literal[*RPC_DBGFLAGS.__members__]] | None = None  # type: ignore[valid-type]


class NFSGetDebugArgs(BaseModel):
    pass


class NFSGetDebugResult(BaseModel):
    result: NfsDebug


class NFSSetDebugArgs(BaseModel):
    svcs: NfsDebug


class NFSSetDebugResult(BaseModel):
    result: bool


def get_debug() -> NfsDebug:
    """
    Display current debug settings for NFS, NFSD, NLM and RPC
    All settings are reported as uppercase.
    See man (8) rpcdebug for more information.
    """
    output: dict[str, list[str]] = {}
    with suppress(FileNotFoundError):
        for svc in os.listdir(SUNRPC_DIR):
            flags: list[str] = []
            if not svc.endswith("debug"):
                continue

            svc_name = svc.upper().split("_")[0]
            with open(os.path.join(SUNRPC_DIR, svc), "r") as f:
                val = int(f.readline().strip(), 16)

            dbgcls = DBGCLS[svc_name]
            for dbgflg in dbgcls:
                if dbgflg.name == "NONE":
                    continue

                if not (val & dbgflg.value):
                    continue

                if dbgflg.name == "ALL" and dbgflg.value != val:
                    continue

                flags.append(dbgflg.name)

            if not flags:
                flags = [dbgcls.NONE.name]

            if dbgcls.ALL.name in flags:
                flags = [dbgcls.ALL.name]

            output[svc_name] = flags

    return NfsDebug.model_validate(output)


def set_debug(services: NfsDebug) -> bool:
    """
    Set debug flags for NFS, NFSD, NLM and RPC.
    All flag names are uppercase.
    See man (8) rpcdebug for more information.
    """

    def debug_level_to_int(svc: str, opts: list[str]) -> int:
        rv = 0

        if "NONE" in opts:
            return rv

        for x in opts:
            rv = rv | DBGCLS[svc][x].value

        return rv

    changes = {svc: opts for svc, opts in services.model_dump().items() if opts is not None}
    for svc, opts in changes.items():
        if opts == []:
            continue
        if "NONE" in opts and len(opts) > 1:
            raise ValueError(f"Cannot specify another value with NONE: {svc}={opts}")

        to_set = "0x%0.4X" % debug_level_to_int(svc, opts)

        with open(os.path.join(SUNRPC_DIR, f"{svc.lower()}_debug"), "w") as f:
            f.write(to_set)

    return True
