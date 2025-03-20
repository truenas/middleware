import os

from contextlib import suppress
from middlewared.api import api_method
from middlewared.api.base import (BaseModel, UniqueList)
from middlewared.service import Service
from typing import Optional

import enum


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


class NFSD_DBGFLAGS(enum. Enum):
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
    ALL = 0x7fff


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
    ALL = 0x7fff


class NfsDebug(BaseModel):
    NFS: Optional[UniqueList[NFS_DBGFLAGS.__members__]] | None = None
    NFSD: Optional[UniqueList[NFSD_DBGFLAGS.__members__]] | None = None
    NLM: Optional[UniqueList[NLM_DBGFLAGS.__members__]] | None = None
    RPC: Optional[UniqueList[RPC_DBGFLAGS.__members__]] | None = None


class NfsDebugGetArgs(BaseModel):
    pass


class NfsDebugGetResult(BaseModel):
    result: dict


class NfsDebugSetArgs(BaseModel):
    svcs: NfsDebug


class NfsDebugSetResult(BaseModel):
    result: bool


class NFSService(Service):
    '''
    NFSService class holds the functions to set and get the debug flags
    for nfs_debug, nfsd_debug, nlm_debug and rpc_debug.  All of these
    are files in /proc/sys/sunrpc.
    '''

    dbgcls = {'NFS': NFS_DBGFLAGS, 'NFSD': NFSD_DBGFLAGS, 'NLM': NLM_DBGFLAGS, 'RPC': RPC_DBGFLAGS}

    @api_method(NfsDebugGetArgs, NfsDebugGetResult, private=True)
    def get_debug(self):
        '''
        Display current debug settings for NFS, NFSD, NLM and RPC
        All settings are reported as uppercase.
        See man (8) rpcdebug for more information.
        '''
        output = {}
        with suppress(FileNotFoundError):
            for svc in os.listdir("/proc/sys/sunrpc"):
                flags = []
                if not svc.endswith("debug"):
                    continue

                svc_name = svc.upper().split('_')[0]
                with open(f"/proc/sys/sunrpc/{svc}", "r") as f:
                    val = int(f.readline().strip(), 16)

                for dbgflg in self.dbgcls[svc_name]:
                    if dbgflg.name == 'NONE':
                        continue

                    if not (val & dbgflg.value):
                        continue

                    if dbgflg.name == 'ALL' and dbgflg.value != val:
                        continue

                    flags.append(dbgflg.name)

                if not flags:
                    flags = [dbgflg.NONE.name]

                if dbgflg.ALL.name in flags:
                    flags = [dbgflg.ALL.name]

                output[svc_name] = flags

        return output

    @api_method(NfsDebugSetArgs, NfsDebugSetResult, private=True)
    def set_debug(self, services):
        '''
        Set debug flags for NFS, NFSD, NLM and RPC.
        All flag names are uppercase.
        See man (8) rpcdebug for more information.
        '''
        def debug_level_to_int(svc, opts):
            rv = 0

            if "NONE" in opts:
                return rv

            for x in opts:
                rv = rv | self.dbgcls[svc][x].value

            return rv

        changes = dict(filter(lambda item: item[1] is not None, services.items()))
        for svc, opts in changes.items():
            if opts == []:
                continue
            if "NONE" in opts and len(opts) > 1:
                raise ValueError(f"Cannot specify another value with NONE: {svc}={opts}")

            to_set = "0x%0.4X" % debug_level_to_int(svc, opts)

            with open(f"/proc/sys/sunrpc/{svc.lower()}_debug", "w") as f:
                f.write(to_set)

        return True
