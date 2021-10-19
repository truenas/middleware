import traceback

import collectd

from middlewared.client import Client

collectd.info('Loading "cputemp" python plugin')


class CpuTemp(object):
    initialized = False

    def config(self, config):
        pass

    def init(self):
        pass

    def read(self):
        try:
            with Client() as c:
                temperatures = c.call('reporting.cpu_temperatures')

            for cpu, temp in temperatures.items():
                temp = 2732 + int(temp * 10)

                val = collectd.Values()
                val.plugin = 'cputemp'
                val.plugin_instance = cpu
                val.type = 'temperature'
                val.values = [temp]
                val.meta = {'0': True}
                val.dispatch()
        except Exception:
            collectd.error(traceback.format_exc())


cputemp = CpuTemp()

collectd.register_config(cputemp.config)
collectd.register_init(cputemp.init)
collectd.register_read(cputemp.read)
