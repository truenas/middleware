from middlewared.schema import accepts, List, Str
from middlewared.service import Service, private
from contextlib import suppress

import os
import enum


class NFSDBG(enum.Flag):
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


class NFSService(Service):

    @private
    def get_debug(self):
        output = {}
        with suppress(FileNotFoundError):
            for svc in os.listdir("/proc/sys/sunrpc"):
                flags = []
                if not svc.endswith("debug"):
                    continue

                with open(f"proc/sys/sunrpc/{svc}", "r") as f:
                    val = int(f.readline().strip(), 16)

                for f in NFSDBG:
                    if f.name == 'NONE':
                        continue

                    if not val & f.value:
                        continue

                    flags.append(f.name)

                if not flags:
                    flags = [NFSDBG.NONE.name]

                if NFSDBG.ALL.name in flags:
                    flags = [NFSDBG.ALL.name]

                output[svc.upper().split("_")[0]] = flags

        return output

    @private
    @accepts(
        List("services", items=[Str("svc", enum=["NFS", "NFSD", "NLM", "RPC"])]),
        List("debug_level", items=[Str("debug_option", enum=[x.name for x in NFSDBG])])
    )
    def set_debug(self, services, debug_level):
        def debug_level_to_int(lvl):
            rv = 0
            if "NONE" in lvl:
                return rv

            for x in lvl:
                rv += NFSDBG[x].value

            return rv

        to_set = "0x%0.4X" % debug_level_to_int(debug_level)
        for svc in services:
            with open(f"/proc/sys/sunrpc/{svc.lower()}_debug", "w") as f:
                f.write(to_set)
