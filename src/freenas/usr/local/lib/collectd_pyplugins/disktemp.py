import traceback

import collectd

from middlewared.client import Client, CallTimeout

READ_INTERVAL = 300.0


class DiskTemp():
    def config(self, config):
        pass

    def init(self):
        collectd.info('Initializing "disktemp" plugin')

    def read(self):
        try:
            with Client() as c:
                for disk, temp in filter(lambda x: x[1] is not None, c.call('disk.read_temps').items()):
                    self.dispatch_value(disk, 'temperature', temp, data_type='temperature')
        except CallTimeout:
            pass
        except Exception:
            collectd.error(traceback.format_exc())

    def dispatch_value(self, name, instance, value, data_type=None):
        val = collectd.Values()
        val.plugin = 'disktemp'
        val.plugin_instance = name
        if data_type:
            val.type = data_type
        val.values = [value]
        val.meta = {'0': True}
        val.dispatch(interval=READ_INTERVAL)


disktemp = DiskTemp()

collectd.register_config(disktemp.config)
collectd.register_init(disktemp.init)
collectd.register_read(disktemp.read, READ_INTERVAL)
