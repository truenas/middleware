import traceback

import collectd

READ_INTERVAL = 10.0

collectd.info('Loading "nfsstat" python plugin')


class NFSStat(object):
    # fs/nfsd/stats.h
    def parse_entries(self, op, parsed, entries, data):
        for idx, name in enumerate(entries):
            data[op][name] = int(parsed[idx])

    def parse_repcache(self, parsed, data):
        """
        reply cache hits, misses, and uncached requests
        """
        entries = [
            "rchits",
            "rcmisses",
            "rcnocache"
        ]
        self.parse_entries("server", parsed, entries, data)

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
        entries = [
            "net_cnt",
            "net_udp_cnt",
            "net_tcp_cnt",
            "net_tcp_conn"
        ]
        self.parse_entries("server", parsed, entries, data)

    def parse_rpc(self, parsed, data):
        entries = [
            "rpc_cnt",
            "rpc_bad_cnt",
            "rpc_bad_fmt",
            "rpc_bad_auth",
            "rpc_bad_clnt"
        ]
        self.parse_entries("server", parsed, entries, data)

    def parse_proc3(self, parsed, data):
        # generic read/write counters for consistency
        # with how we reported from Ganesha
        data["server"]["read"] = int(parsed[7])
        data["server"]["write"] = int(parsed[8])

        # NFSv3 operations counters
        # skip NULL op
        entries = [
            "nfsv3_op_null",
            "nfsv3_op_getattr",
            "nfsv3_op_setattr",
            "nfsv3_op_lookup",
            "nfsv3_op_access",
            "nfsv3_op_readlink",
            "nfsv3_op_read",
            "nfsv3_op_write",
            "nfsv3_op_create",
            "nfsv3_op_mkdir",
            "nfsv3_op_symlink",
            "nfsv3_op_mknod",
            "nfsv3_op_remove",
            "nfsv3_op_rmdir",
            "nfsv3_op_rename",
            "nfsv3_op_link",
            "nfsv3_op_readdir",
            "nfsv3_op_readdirplus",
            "nfsv3_op_fsstat",
            "nfsv3_op_fsinfo",
            "nfsv3_op_pathconf",
            "nfsv3_op_commit"
        ]
        self.parse_entries("nfsv3_ops", parsed[1:], entries, data)

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
        # NFSv41 ops begin with "nfsv4_op_backchannel_ctl"
        # NFSv42 ops begin with "nfsv4_op_allocate"
        # RFC 8726 (xattr) support begins with "nfsv4_op_getxattr"
        entries = [
            "nfsv4_op_access",
            "nfsv4_op_close",
            "nfsv4_op_commit",
            "nfsv4_op_create",
            "nfsv4_op_delegpurge",
            "nfsv4_op_delegreturn",
            "nfsv4_op_getattr",
            "nfsv4_op_getfh",
            "nfsv4_op_link",
            "nfsv4_op_lock",
            "nfsv4_op_lockt",
            "nfsv4_op_locku",
            "nfsv4_op_lookup",
            "nfsv4_op_lookupp",
            "nfsv4_op_nverify",
            "nfsv4_op_open",
            "nfsv4_op_openattr",
            "nfsv4_op_open_confirm",
            "nfsv4_op_open_downgrade",
            "nfsv4_op_putfh",
            "nfsv4_op_putpubfh",
            "nfsv4_op_putrootfh",
            "nfsv4_op_read",
            "nfsv4_op_readdir",
            "nfsv4_op_readlink",
            "nfsv4_op_remove",
            "nfsv4_op_rename",
            "nfsv4_op_renew",
            "nfsv4_op_restorefh",
            "nfsv4_op_savefh",
            "nfsv4_op_secinfo",
            "nfsv4_op_setattr",
            "nfsv4_op_setclientid",
            "nfsv4_op_setclientid_confirm",
            "nfsv4_op_verify",
            "nfsv4_op_write",
            "nfsv4_op_release_lock_owner",
            "nfsv4_op_backchannel_ctl",
            "nfsv4_op_bind_conn_to_session",
            "nfsv4_op_exchange_id",
            "nfsv4_op_create_session",
            "nfsv4_op_destroy_session",
            "nfsv4_op_free_stateid",
            "nfsv4_op_get_dir_delegation",
            "nfsv4_op_getdeviceinfo",
            "nfsv4_op_getdevicelist",
            "nfsv4_op_layoutcommmit",
            "nfsv4_op_layoutget",
            "nfsv4_op_layoutreturn",
            "nfsv4_op_secinfo_no_name",
            "nfsv4_op_sequence",
            "nfsv4_op_set_ssv",
            "nfsv4_op_test_stateid",
            "nfsv4_op_want_delegation",
            "nfsv4_op_destroy_clientid",
            "nfsv4_op_reclaim_complete",
            "nfsv4_op_allocate",
            "nfsv4_op_copy",
            "nfsv4_op_copy_notify",
            "nfsv4_op_deallocate",
            "nfsv4_op_io_advise",
            "nfsv4_op_layouterror",
            "nfsv4_op_layoutstats",
            "nfsv4_op_offload_cancel",
            "nfsv4_op_offload_status",
            "nfsv4_op_read_plus",
            "nfsv4_op_seek",
            "nfsv4_op_write_same",
            "nfsv4_op_clone",
            "nfsv4_op_getxattr",
            "nfsv4_op_setxattr",
            "nfsv4_op_listxattrs",
            "nfsv4_op_removexattr",
        ]
        self.parse_entries("nfsv4_ops", parsed[2:], entries, data)

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
        data = {
            "server": {"read": 0, "write": 0, "read_bytes": 0, "write_bytes": 0},
            "nfsv3_ops": {},
            "nfsv4_ops": {}
        }
        try:
            with open("/proc/net/rpc/nfsd", "r") as f:
                for line in f:
                    parsed = line.split()
                    if parsed[0] in self.ignored:
                        continue

                    self.op_table[parsed[0]](self, parsed[1:], data)

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
