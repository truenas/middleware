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
import asyncio
import re
import subprocess
import sysctl

# One cannot simply import collectd in a python interpreter (for various reasons)
# thus adding this workaround for standalone testing
if __name__ == '__main__':
    class CollectdDummy:
        def register_config(self, a):
            # do something
            pass

        def register_init(self, a):
            a()

        def register_read(self, a, b=10):
            a()

        def info(self, msg):
            print(msg)

        def warning(self, msg):
            print(msg)

        def debug(self, msg):
            print(msg)

        def error(self, msg):
            print(msg)

        class Values(object):
            def __init__(self, *args, **kwargs):
                self.plugin = ''
                self.plugin_instance = ''
                self.type = None
                self.type_instance = None
                self.values = None
                self.meta = None

            def dispatch(self):
                print(f'{self.plugin}:{self.plugin_instance}:{self.type}:{self.type_instance}:{self.values}')

    collectd = CollectdDummy()
else:
    import collectd


READ_INTERVAL = 300


collectd.info('Loading "disktemp" python plugin')


class DiskTemp(object):

    def init(self):
        collectd.debug('Initializing "disktemp" plugin')

    def read(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.loop())

    def dispatch_value(self, name, instance, value, data_type='gauge'):
        val = collectd.Values()
        val.plugin = 'disktemp'
        val.plugin_instance = name
        val.type = data_type
        val.type_instance = instance
        val.values = [value, ]
        val.meta = {'0': True}
        val.dispatch()

    async def loop(self):
        while True:
            disks = sysctl.filter('kern.disks')[0].value.split()
            futures = {}
            for disk in disks:
                if disk.startswith('cd'):
                    continue
                futures[asyncio.ensure_future(self.get_temperature(disk))] = disk

            done = (await asyncio.wait(futures, timeout=10))[0]
            for task in done:
                disk = futures.get(task)
                if not disk:
                    continue
                temp = task.result()
                if temp is None:
                    continue
                self.dispatch_value(disk, 'temperature', temp)

            await asyncio.sleep(READ_INTERVAL)

    async def get_temperature(self, disk):
        proc = await asyncio.create_subprocess_exec('smartctl', '-a', '-n', 'standby', f'/dev/{disk}', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
            stdout = stdout.decode('utf8', 'ignore')
            if proc.returncode != 0:
                return None
            reg = re.search(r'190\s+Airflow_Temperature_Cel[^\n]*', stdout, re.M)
            if reg:
                return int(reg.group(0).split()[9])

            reg = re.search(r'194\s+Temperature_Celsius[^\n]*', stdout, re.M)
            if reg:
                return int(reg.group(0).split()[9])
        except asyncio.TimeoutError:
            return None


disktemp = DiskTemp()

collectd.register_init(disktemp.init)
collectd.register_read(disktemp.read)
