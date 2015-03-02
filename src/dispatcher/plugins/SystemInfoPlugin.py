# +
# Copyright 2014 iXsystems, Inc.
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

import os
import sys
import psutil
import time
from datetime import datetime
from dateutil import tz
from dispatcher.rpc import description, returns
from task import Provider, Task
from lib.system import system, system_bg
from lib.freebsd import get_sysctl


@description("Provides informations about the running system")
class SystemInfoProvider(Provider):

    def uname_full(self):
        out, _ = system('uname', '-a')
        return out

    def version(self):
        with open('/etc/version') as fd:
            return fd.read().strip()

    def hardware(self):
        return {
            'cpu-model': get_sysctl("hw.model"),
            'cpu-cores': get_sysctl("hw.ncpu"),
            'memory-size': get_sysctl("hw.physmem")
        }

    def time(self):
        return {
            'system-time': datetime.now(tz=tz.tzlocal()),
            'boot-time': datetime.fromtimestamp(psutil.BOOT_TIME, tz=tz.tzlocal()).isoformat(),
            'timezone': time.tzname[time.daylight],
        }

    def timezones(self):
        result = []
        for root, _, files in os.walk(sys.argv[1]):
            for f in files:
                result.append(os.path.join(root, f))

        return result


class ConfigureTimeTask(Task):
    def verify(self):
        return ['system']

    def run(self, updated_props):
        pass

@description("Reboots the System after a delay of 10 seconds")
class SystemRebootTask(Task):
    def describe(self):
        return "System Reboot"

    def verify(self):
        return ['root']

    def run(self, delay=10):
        self.dispatcher.dispatch_event('power.changed', {
            'operation': 'reboot',
            })
        system_bg("/bin/sleep %s && /sbin/shutdown -r now &" % delay,
                  shell=True)

@description("Shuts the system down after a delay of 10 seconds")
class SystemHaltTask(Task):
    def describe(self):
        return "System Shutdown"

    def verify(self):
        return ['root']

    def run(self, delay=10):
        self.dispatcher.dispatch_event('power.changed', {
            'operation': 'shutdown',
            })
        system_bg("/bin/sleep %s && /sbin/shutdown -p now &" % delay,
                  shell=True)


def _init(dispatcher):
    # Register providers
    dispatcher.register_provider("system.info", SystemInfoProvider)

    # Register task handlers
    dispatcher.register_task_handler("system.shutdown", SystemHaltTask)
    dispatcher.register_task_handler("system.reboot", SystemRebootTask)
