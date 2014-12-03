#+
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
import errno
from gevent.event import Event
from lib import zfs
from lib.system import system, SubprocessException
from task import Provider, Task, TaskStatus, TaskException
from dispatcher.rpc import accepts, returns, description
from balancer import TaskState


class DiskProvider(Provider):
    def query(self, filter=None, params=None):
        pass


class DiskGPTFormatTask(Task):
    def describe(self, disk, type, swapsize=2048, params=None):
        return "Formatting disk {0}".format(os.path.basename(disk))

    def verify(self, disk, params=None):
        pass

    def run(self, disk, typename, params=None):
        if params is None:
            params = {}

        blocksize = params.pop('blocksize', 4096)
        swapsize = params.pop('swapsize', '2048M')
        bootcode = params.pop('bootcode', '/boot/pmbr-datadisk')

        try:
            system('gpart', 'destroy', '-F', disk)
        except SubprocessException:
            # ignore
            pass

        try:
            system('gpart', 'create', '-s', 'gpt', disk)

            if swapsize > 0:
                system('gpart', 'add', '-a', str(blocksize), '-b', '128', '-s', swapsize, '-t', 'freebsd-swap', disk)
                system('gpart', 'add', '-a', str(blocksize), '-t', typename)
            else:
                system('gpart', 'add', '-a', str(blocksize), '-b', '128', '-t', typename)

            system('gpart', 'bootcode', '-b', bootcode, disk)
        except SubprocessException, err:
            raise TaskException(errno.EFAULT, 'Cannot format disk: {0}'.format(str(err)))


def _init(dispatcher):
    dispatcher.register_provider('disk', DiskProvider)
    dispatcher.register_task_handler('disk.format', DiskGPTFormatTask)