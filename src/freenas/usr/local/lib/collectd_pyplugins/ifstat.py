import traceback

import collectd
from pyroute2 import IPRoute

from middlewared.client import Client

READ_INTERVAL = 1.0


class IfStat():
    ignore = []

    def config(self, config):
        pass

    def init(self):
        collectd.info('Initializing "ifstat" python plugin')
        try:
            with Client() as c:
                self.ignore = c.call('interface.internal_interfaces')
        except Exception:
            collectd.error(traceback.format_exc())

    def valid_iface(self, dev):
        ifname = dev.get_attr('IFLA_IFNAME')
        if ifname is not None and ifname not in self.ignore:
            return ifname

    def get_stats(self):
        stats = dict()
        with IPRoute() as ipr:
            for i in ipr.dump():
                if ifname := self.valid_iface(i):
                    if ifstats := i.get_attr('IFLA_STATS64'):
                        stats[ifname] = ifstats
        return stats

    def read(self):
        try:
            stats = self.get_stats()
        except Exception:
            collectd.error(traceback.format_exc())
        else:
            for ifname, ifstats in stats.items():
                for stat, value in ifstats.items():
                    self.dispatch_value(ifname, stat, value)

    def dispatch_value(self, ifname, stat, value):
        val = collectd.Values()
        val.plugin = 'ifstat'
        val.plugin_instance = ifname
        val.type = 'ifstat'
        val.type_instance = stat
        val.values = [value]
        val.meta = {'0': True}
        val.dispatch(interval=READ_INTERVAL)


ifstat = IfStat()
collectd.register_config(ifstat.config)
collectd.register_init(ifstat.init)
collectd.register_read(ifstat.read, READ_INTERVAL)
