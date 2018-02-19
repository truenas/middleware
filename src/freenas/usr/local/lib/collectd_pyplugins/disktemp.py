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
import concurrent.futures
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

    def dispatch_value(self, name, instance, value, data_type=None):
        val = collectd.Values()
        val.plugin = 'disktemp'
        val.plugin_instance = name
        if data_type:
            val.type = data_type
        val.values = [value, ]
        val.meta = {'0': True}
        val.dispatch()

    def read(self):
        disks = sysctl.filter('kern.disks')[0].value.split()
        futures = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for disk in disks:
                if disk.startswith('cd'):
                    continue
                futures[executor.submit(self.get_temperature, disk)] = disk

            for fut in concurrent.futures.as_completed(futures.keys()):
                disk = futures.get(fut)
                if not disk:
                    continue
                try:
                    temp = fut.result()
                    if temp is None:
                        continue
                    self.dispatch_value(disk, 'temperature', temp, data_type='temperature')
                except Exception as e:
                    pass

    def get_temperature(self, disk):
        cp = subprocess.run(['/usr/local/sbin/smartctl', '-a', '-n', 'standby', f'/dev/{disk}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode != 0:
            return None
        stdout = cp.stdout.decode('utf8', 'ignore')
        reg = re.search(r'190\s+Airflow_Temperature_Cel[^\n]*', stdout, re.M)
        if reg:
            return int(reg.group(0).split()[9])

        reg = re.search(r'194\s+Temperature_Celsius[^\n]*', stdout, re.M)
        if reg:
            return int(reg.group(0).split()[9])
        return None


disktemp = DiskTemp()

collectd.register_init(disktemp.init)
collectd.register_read(disktemp.read, READ_INTERVAL)
