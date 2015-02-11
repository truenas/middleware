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

from dispatcher.rpc import description
from task import Provider, Task
from lib.system import system
from lib.freebsd import get_sysctl


@description("Provides informations about the running system")
class SystemInfoProvider(Provider):

    def uname_full(self):
        out, _ = system('uname', '-a')
        return out

    def memory_size(self):
        return get_sysctl("hw.realmem")

    def cpu_model(self):
        return get_sysctl("hw.model")

    def logged_users(self):
        result = []
        out, err = system('w')
        for line in out.split('\n'):
            parts = line.split(None, 6)
            result.append({
                'username': parts[0],
                'tty': parts[1],
                'host': parts[2],
                'login-at': parts[3],
                'idle': parts[4],
                'command': parts[5]
            })


class SystemRebootTask(Task):
    def verify(self):
        return ['root']

    def run(self):
        system('/sbin/shutdown', '-r', 'now')


class SystemHaltTask(Task):
    def verify(self):
        return ['root']

    def run(self):
        system('/sbin/shutdown', '-p', 'now')


def _init(dispatcher):
    # Register providers
    dispatcher.register_provider("system.info", SystemInfoProvider)

    # Register task handlers
    dispatcher.register_task_handler("system.shutdown", SystemHaltTask)
    dispatcher.register_task_handler("system.reboot", SystemRebootTask)
