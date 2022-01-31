import traceback

import collectd

READ_INTERVAL = 10.0

collectd.info('Loading "nfsstat" python plugin')


class NFSStat(object):
    def config(self, config):
        pass

    def init(self):
        self.errors = set()

    def read(self):
        try:
            read_bytes = 0
            write_bytes = 0
            read_ops = 0
            write_ops = 0
            with open("/proc/net/rpc/nfsd", "r") as f:
                for line in f:
                    if line.startswith('io'):
                        parsed = line.split()
                        read_bytes = int(parsed[1])
                        write_bytes = int(parsed[2])
                        continue

                    if line.startswith('proc3'):
                        parsed = line.split()
                        read_ops = int(parsed[8])
                        write_ops = int(parsed[9])

                    if line.startswith('proc4ops'):
                        parsed = line.split()
                        read_ops += int(parsed[27])
                        write_ops += int(parsed[40])
                        continue

            self.dispatch_value('read', read_ops)
            self.dispatch_value('write', write_ops)
            self.dispatch_value('read_bytes', read_bytes)
            self.dispatch_value('write_bytes', write_bytes)
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
