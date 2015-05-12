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
import psutil
import re
import sys
import time

from datetime import datetime
from dateutil import tz
from dispatcher.rpc import SchemaHelper as h, accepts, description, returns
from lib.system import system, system_bg
from lib.freebsd import get_sysctl
from task import Provider, Task


KEYMAPS_INDEX = "/usr/share/syscons/keymaps/INDEX.keymaps"


@description("Provides informations about the running system")
class SystemInfoProvider(Provider):
    @returns(str)
    def uname_full(self):
        out, _ = system('uname', '-a')
        return out

    @returns(str)
    def version(self):
        with open('/etc/version') as fd:
            return fd.read().strip()

    def hardware(self):
        return {
            'cpu-model': get_sysctl("hw.model"),
            'cpu-cores': get_sysctl("hw.ncpu"),
            'memory-size': get_sysctl("hw.physmem")
        }

    def keymaps(self):
        if not os.path.exists(KEYMAPS_INDEX):
            return []

        rv = []
        with open(KEYMAPS_INDEX, 'r') as f:
            d = f.read()
        fnd = re.findall(r'^(?P<name>[^#\s]+?)\.kbd:en:(?P<desc>.+)$', d, re.M)
        for name, desc in fnd:
            rv.append((name, desc))
        return rv

    def time(self):
        return {
            'system-time': datetime.now(tz=tz.tzlocal()),
            'boot-time': datetime.fromtimestamp(
                psutil.BOOT_TIME, tz=tz.tzlocal()
            ).isoformat(),
            'timezone': time.tzname[time.daylight],
        }

    def timezones(self):
        result = []
        for root, _, files in os.walk(sys.argv[1]):
            for f in files:
                result.append(os.path.join(root, f))
        return result


@accepts(h.ref('system-settings'))
class SystemConfigureTask(Task):

    def describe(self):
        return "System Settings Configure"

    def verify(self):
        return ['system']

    def run(self, props):
        self.dispatcher.configstore.set(
            'service.nginx.http.enable',
            True if 'HTTP' in props.get('webui-procotol') else False,
        )
        self.dispatcher.configstore.set(
            'service.nginx.https.enable',
            True if 'HTTPS' in props.get('webui-procotol') else False,
        )
        self.dispatcher.configstore.set(
            'service.nginx.listen',
            props.get('webui-listen'),
        )
        self.dispatcher.configstore.set(
            'service.nginx.http.port',
            props.get('webui-http-port'),
        )
        self.dispatcher.configstore.set(
            'service.nginx.https.port',
            props.get('webui-https-port'),
        )
        self.dispatcher.configstore.set(
            'system.language',
            props.get('language'),
        )
        self.dispatcher.configstore.set(
            'system.timezone',
            props.get('timezone'),
        )
        self.dispatcher.configstore.set(
            'system.console.keymap',
            props.get('console-keymap'),
        )


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

    # Register schemas
    dispatcher.register_schema_definition('system-settings', {
        'type': 'object',
        'properties': {
            'webui-protocol': {
                'type': ['array'],
                'items': {
                    'type': 'string',
                    'enum': ['HTTP', 'HTTPS'],
                },
            },
            'webui-listen': {
                'type': ['array'],
                'items': {'type': 'string'},
            },
            'webui-http-port': {
                'type': ['array'],
                'items': {'type': 'integer'},
            },
            'webui-https-port': {
                'type': ['array'],
                'items': {'type': 'integer'},
            },
            'language': {'type': 'string'},
            'timezone': {'type': 'string'},
            'console-keymap': {'type': 'string'},
        },
    })

    # Register providers
    dispatcher.register_provider("system.info", SystemInfoProvider)

    # Register task handlers
    dispatcher.register_task_handler("system.configure", SystemConfigureTask)
    dispatcher.register_task_handler("system.shutdown", SystemHaltTask)
    dispatcher.register_task_handler("system.reboot", SystemRebootTask)
