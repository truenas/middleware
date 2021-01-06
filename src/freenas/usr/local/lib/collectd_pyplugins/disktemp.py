# Copyright 2018 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import traceback

import collectd

from middlewared.client import Client, CallTimeout

READ_INTERVAL = 300.0

collectd.info('Loading "disktemp" python plugin')


class DiskTemp(object):
    initialized = False

    def config(self, config):
        pass

    def init(self):
        collectd.info('Initializing "disktemp" plugin')
        try:
            with Client() as c:
                self.disks = c.call('disk.disks_for_temperature_monitoring')
                self.powermode = c.call('smart.config')['powermode']
        except Exception:
            collectd.error(traceback.format_exc())
        else:
            self.initialized = True

    def read(self):
        if not self.initialized:
            self.init()

        if not self.initialized:
            return

        if not self.disks:
            return

        try:
            with Client() as c:
                temperatures = c.call('disk.temperatures', self.disks, self.powermode)

            for disk, temp in temperatures.items():
                if temp is not None:
                    self.dispatch_value(disk, 'temperature', temp, data_type='temperature')
        except CallTimeout:
            collectd.error("Timeout collecting disk temperatures")
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
