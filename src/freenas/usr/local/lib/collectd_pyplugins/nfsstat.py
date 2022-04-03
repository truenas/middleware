import traceback

import collectd
import enum
from contextlib import suppress

READ_INTERVAL = 10.0

collectd.info('Loading "nfsstat" python plugin')


class ReplyCache(enum.IntEnum):
    RC_HITS = 0
    RC_MISSES = enum.auto()
    RC_NOCACHE = enum.auto()


class Net(enum.IntEnum):
    NET_CNT = 0
    NET_UDP_CNT = enum.auto()
    NET_TCP_CNT = enum.auto()
    NET_TCP_CONN = enum.auto()


class Rpc(enum.IntEnum):
    RPC_CNT = 0
    RPC_BAD_CNT = enum.auto()
    RPC_BAD_FMT = enum.auto()
    RPC_BAD_AUTH = enum.auto()
    RPC_BAD_CLNT = enum.auto()


class NFSv3_OP(enum.IntEnum):
    NFSV3_OP_NULL = 0
    NFSV3_OP_GETATTR = enum.auto()
    NFSV3_OP_SETATTR = enum.auto()
    NFSV3_OP_LOOKUP = enum.auto()
    NFSV3_OP_ACCESS = enum.auto()
    NFSV3_OP_READLINK = enum.auto()
    NFSV3_OP_READ = enum.auto()
    NFSV3_OP_WRITE = enum.auto()
    NFSV3_OP_CREATE = enum.auto()
    NFSV3_OP_MKDIR = enum.auto()
    NFSV3_OP_SYMLINK = enum.auto()
    NFSV3_OP_MKNOD = enum.auto()
    NFSV3_OP_REMOVE = enum.auto()
    NFSV3_OP_RMDIR = enum.auto()
    NFSV3_OP_RENAME = enum.auto()
    NFSV3_OP_LINK = enum.auto()
    NFSV3_OP_READDIR = enum.auto()
    NFSV3_OP_READDIRPLUS = enum.auto()
    NFSV3_OP_FSSTAT = enum.auto()
    NFSV3_OP_FSINFO = enum.auto()
    NFSV3_OP_PATHCONF = enum.auto()


class NFSv4_OP(enum.IntEnum):
    NFSV4_OP_ACCESS = 3
    NFSV4_OP_CLOSE = enum.auto()
    NFSV4_OP_COMMIT = enum.auto()
    NFSV4_OP_CREATE = enum.auto()
    NFSV4_OP_DELEGPURGE = enum.auto()
    NFSV4_OP_DELEGRETURN = enum.auto()
    NFSV4_OP_GETATTR = enum.auto()
    NFSV4_OP_GETFH = enum.auto()
    NFSV4_OP_LINK = enum.auto()
    NFSV4_OP_LOCK = enum.auto()
    NFSV4_OP_LOCKT = enum.auto()
    NFSV4_OP_LOCKU = enum.auto()
    NFSV4_OP_LOOKUP = enum.auto()
    NFSV4_OP_LOOKUPP = enum.auto()
    NFSV4_OP_NVERIFY = enum.auto()
    NFSV4_OP_OPEN = enum.auto()
    NFSV4_OP_OPENATTR = enum.auto()
    NFSV4_OP_OPEN_CONFIRM = enum.auto()
    NFSV4_OP_OPEN_DOWNGRADE = enum.auto()
    NFSV4_OP_PUTFH = enum.auto()
    NFSV4_OP_PUTPUBFH = enum.auto()
    NFSV4_OP_PUTROOTFH = enum.auto()
    NFSV4_OP_READ = enum.auto()
    NFSV4_OP_READDIR = enum.auto()
    NFSV4_OP_READLINK = enum.auto()
    NFSV4_OP_REMOVE = enum.auto()
    NFSV4_OP_RENAME = enum.auto()
    NFSV4_OP_RENEW = enum.auto()
    NFSV4_OP_RESTOREFH = enum.auto()
    NFSV4_OP_SAVEFH = enum.auto()
    NFSV4_OP_SECINFO = enum.auto()
    NFSV4_OP_SETATTR = enum.auto()
    NFSV4_OP_SETCLIENTID = enum.auto()
    NFSV4_OP_SETCLIENTID_CONFIRM = enum.auto()
    NFSV4_OP_VERIFY = enum.auto()
    NFSV4_OP_WRITE = enum.auto()
    NFSV4_OP_RELEASE_LOCK_OWNER = enum.auto()
    NFSV4_OP_BACKCHANNEL_CTL = enum.auto()
    NFSV4_OP_BIND_CONN_TO_SESSION = enum.auto()
    NFSV4_OP_EXCHANGE_ID = enum.auto()
    NFSV4_OP_CREATE_SESSION = enum.auto()
    NFSV4_OP_DESTROY_SESSION = enum.auto()
    NFSV4_OP_FREE_STATEID = enum.auto()
    NFSV4_OP_GET_DIR_DELEGATION = enum.auto()
    NFSV4_OP_GETDEVICEINFO = enum.auto()
    NFSV4_OP_GETDEVICELIST = enum.auto()
    NFSV4_OP_LAYOUTCOMMMIT = enum.auto()
    NFSV4_OP_LAYOUTGET = enum.auto()
    NFSV4_OP_LAYOUTRETURN = enum.auto()
    NFSV4_OP_SECINFO_NO_NAME = enum.auto()
    NFSV4_OP_SEQUENCE = enum.auto()
    NFSV4_OP_SET_SSV = enum.auto()
    NFSV4_OP_TEST_STATEID = enum.auto()
    NFSV4_OP_WANT_DELEGATION = enum.auto()
    NFSV4_OP_DESTROY_CLIENTID = enum.auto()
    NFSV4_OP_RECLAIM_COMPLETE = enum.auto()
    NFSV4_OP_ALLOCATE = enum.auto()
    NFSV4_OP_COPY = enum.auto()
    NFSV4_OP_COPY_NOTIFY = enum.auto()
    NFSV4_OP_DEALLOCATE = enum.auto()
    NFSV4_OP_IO_ADVISE = enum.auto()
    NFSV4_OP_LAYOUTERROR = enum.auto()


class ThreadPool(enum.IntEnum):
    PACKETS_ARRIVED = 0
    SOCKETS_ENQUEUED = enum.auto()
    THREADS_WOKEN = enum.auto()
    THREADS_TIMEDOUT = enum.auto()


class NFSStat(object):
    # fs/nfsd/stats.h
    def parse_entries(self, op, parsed, entries, data):
        for i in entries:
            data[op][i.name.lower()] = int(parsed[i])

    def parse_repcache(self, parsed, data):
        """
        reply cache hits, misses, and uncached requests
        """
        self.parse_entries("server", parsed, ReplyCache, data)

    def parse_fh(self, parsed, data):
        """
        Code updating filehandle cache stats was removed
        from linux kernel in 2002, but stats
        themselves were not removed until 2021.

        Hence, although 5.10 kernel has additional stats,
        we do not expose them.
        """
        data["server"]["fh_stale"] = int(parsed[0])

    def parse_io(self, parsed, data):
        data["server"]["read_bytes"] = int(parsed[0])
        data["server"]["write_bytes"] = int(parsed[1])

    def parse_th(self, parsed, data):
        """
        Thread busy counters were removed in 2009.
        Same as above in parse_fh()
        """
        data["server"]["thread_count"] = int(parsed[0])

    def parse_net(self, parsed, data):
        self.parse_entries("server", parsed, Net, data)

    def parse_rpc(self, parsed, data):
        self.parse_entries("server", parsed, Rpc, data)

    def parse_proc3(self, parsed, data):
        # generic read/write counters for consistency
        # with how we reported from Ganesha
        data["server"]["read"] = int(parsed[7])
        data["server"]["write"] = int(parsed[8])

        # NFSv3 operations counters
        self.parse_entries("nfsv3_ops", parsed[1:], NFSv3_OP, data)

    def parse_proc4(self, parsed, data):
        data["server"]["nfsv4_null"] = int(parsed[1])
        data["server"]["nfsv4_compound"] = int(parsed[2])

    def parse_proc4ops(self, parsed, data):
        # generic read/write counters for consistency
        # with how we reported from Ganesha
        data["server"]["read"] += int(parsed[26])
        data["server"]["write"] += int(parsed[39])

        # NFSv4.0, 4.1, 4.2 operations
        # OP numbers are defined in include/linux/nfs4.h
        # First OP is OP_ACCESS (3)
        # NFSv41 ops begin with NFSV4_OP_BACKCHANNEL_CTL
        # NFSv42 ops begin with NFSV4_OP_ALLOCATE
        # RFC 8726 (xattr) support begins with NFSV4_OP_GETXATTR
        self.parse_entries("nfsv4_ops", parsed[1:], NFSv4_OP, data)

    def parse_threadpool_info(self, parsed, data):
        # https://www.kernel.org/doc/Documentation/filesystems/nfs/knfsd-stats.txt
        tp = f'threadpool_{int(parsed[0]):03}'
        data[tp] = {}
        self.parse_entries(tp, parsed[1:], ThreadPool, data)

    op_table = {
        "rc": parse_repcache,
        "fh": parse_fh,
        "io": parse_io,
        "th": parse_th,
        "net": parse_net,
        "rpc": parse_rpc,
        "proc3": parse_proc3,
        "proc4": parse_proc4,
        "proc4ops": parse_proc4ops,
    }

    """
    read-ahead cache stats are deprecated, but still
    present in 5.10 kernel. proc2 is disabled in SCALE.
    Expand the ignored list if we decide that stats are
    excessive.
    """
    ignored = ["ra", "proc2"]

    def config(self, config):
        pass

    def init(self):
        self.errors = set()

    def read(self):
        data = {"server": {}, "nfsv3_ops": {}, "nfsv4_ops": {}}

        """
        /proc/net/rpc/nfsd:

        rc 0 0 0
        fh 0 0 0 0 0
        io 0 0
        th 50 0 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000 0.000
        ra 0 0 0 0 0 0 0 0 0 0 0 0
        net 0 0 0 0
        rpc 0 0 0 0 0
        proc2 18 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
        proc3 22 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
        proc4 2 0 0
        proc4ops 76 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
        """
        with suppress(OSError):
            data["server"] = {"read": 0, "write": 0, "read_bytes": 0, "write_bytes": 0}
            with open("/proc/net/rpc/nfsd", "r") as f:
                for line in f:
                    parsed = line.split()
                    if parsed[0] in self.ignored:
                        continue

                    self.op_table[parsed[0]](self, parsed[1:], data)

        """
        /proc/fs/nfsd/pool_stats:

        # pool packets-arrived sockets-enqueued threads-woken threads-timedout
        0 1 1 0 0
        """
        with suppress(OSError):
            with open("/proc/fs/nfsd/pool_stats", "r") as f:
                for line in f:
                    if line.startswith("#"):
                        continue

                    self.parse_threadpool_info(line.split(), data)

        try:
            for plugin_instance, plugin_data in data.items():
                for type_instance, val in plugin_data.items():
                    self.dispatch_value(plugin_instance, type_instance, val)

        except Exception:
            collectd.error(traceback.format_exc())

    def dispatch_value(self, plugin_instance, type_instance, value):
        val = collectd.Values()
        val.plugin = 'nfsstat'
        val.plugin_instance = plugin_instance
        val.type = 'nfsstat'
        val.type_instance = type_instance
        val.values = [value]
        val.meta = {'0': True}
        val.dispatch(interval=READ_INTERVAL)


nfs_stat = NFSStat()

collectd.register_config(nfs_stat.config)
collectd.register_init(nfs_stat.init)
collectd.register_read(nfs_stat.read, READ_INTERVAL)
