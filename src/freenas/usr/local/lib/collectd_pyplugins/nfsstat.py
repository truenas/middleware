import traceback

import collectd
import dbus

READ_INTERVAL = 10.0

collectd.info('Loading "nfsstat" python plugin')

bus = dbus.SystemBus()
proxy = bus.get_object("org.ganesha.nfsd", "/org/ganesha/nfsd/ExportMgr")
exportmgr = dbus.Interface(proxy, dbus_interface="org.ganesha.nfsd.exportmgr")
exportstats = dbus.Interface(proxy, dbus_interface="org.ganesha.nfsd.exportstats")


class Stats:
    def __init__(self):
        self.read_bytes = 0
        self.read_ops = 0
        self.write_bytes = 0
        self.write_ops = 0

    def add(self, stats):
        if stats[1] == "OK":
            self.read_bytes += stats[3][1]
            self.read_ops += stats[3][2]
            self.write_bytes += stats[4][1]
            self.write_ops += stats[4][2]


class NFSStat(object):
    def config(self, config):
        pass

    def init(self):
        self.errors = set()

    def read(self):
        try:
            stats = Stats()
            for export in exportmgr.ShowExports()[1]:
                export_id, path, v3, v40, v41, v42 = export[:6]

                if v3:
                    try:
                        stats.add(exportstats.GetNFSv3IO(export_id))
                    except Exception:
                        if "v3" not in self.errors:
                            collectd.error(traceback.format_exc())
                            self.errors.add("v3")

                if v40:
                    try:
                        stats.add(exportstats.GetNFSv40IO(export_id))
                    except Exception:
                        if "v40" not in self.errors:
                            collectd.error(traceback.format_exc())
                            self.errors.add("v40")

                if v41:
                    try:
                        stats.add(exportstats.GetNFSv41IO(export_id))
                    except Exception:
                        if "v41" not in self.errors:
                            collectd.error(traceback.format_exc())
                            self.errors.add("v41")

                if v42:
                    try:
                        stats.add(exportstats.GetNFSv42IO(export_id))
                    except Exception:
                        if "v42" not in self.errors:
                            collectd.error(traceback.format_exc())
                            self.errors.add("v42")

            self.dispatch_value('read', stats.read_ops)
            self.dispatch_value('write', stats.write_ops)
            self.dispatch_value('read_bytes', stats.read_bytes)
            self.dispatch_value('write_bytes', stats.write_bytes)
        except Exception:
            collectd.error(traceback.format_exc())

    def dispatch_value(self, type_instance, value):
        val = collectd.Values()
        val.plugin = 'nfsstat'
        val.plugin_instance = 'server'
        val.type = 'nfsstat'
        val.type_instance = type_instance
        val.values = [value]
        val.meta = {'0': True}
        val.dispatch(interval=READ_INTERVAL)


nfs_stat = NFSStat()

collectd.register_config(nfs_stat.config)
collectd.register_init(nfs_stat.init)
collectd.register_read(nfs_stat.read, READ_INTERVAL)
