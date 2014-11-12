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

import errno
from gevent import Timeout
from watchdog import events
from task import Task, TaskStatus, Provider, TaskException
from dispatcher.rpc import description, schema
from balancer import TaskState
from event import EventSource
from lib.system import system, SubprocessException


@description("Provides info about available services and their state")
class ServiceInfoProvider(Provider):
    @description("Lists available services")
    def list_services(self):
        try:
            out, err = system(["/usr/sbin/service", "-l"])
        except SubprocessException, e:
            raise TaskException(errno.ENXIO, e.err)

    def get_service_info(self, service):
        pass


@description("Provides functionality to start, stop, restart or reload service")
@schema({

})
class ServiceManageTask(Task):
    def __init__(self, dispatcher):
        pass

    def describe(self, name, action):
        return "{0}ing service {1}".format(action.title(), name)

    def verify(self, name, action):
        if action not in ('start', 'stop', 'restart', 'reload'):
            raise TaskException(errno.EINVAL, "Invalid action")

        try:
            out, err = system(["/usr/sbin/service", "-l"])
        except SubprocessException, e:
            raise TaskException(errno.ENXIO, e.err)

        if name not in out.split():
            raise TaskException(errno.ENOENT, "No such service")

        return ['system']

    def run(self, name, action):
        try:
            system(["/usr/sbin/service", name, action])
        except SubprocessException, e:
            raise TaskException(errno.EBUSY, e.err)

        return TaskState.FINISHED

    def get_status(self):
        return TaskStatus(None, "Processing...")

    def abort(self):
        # We cannot abort that task
        return False

def _init(dispatcher):
    dispatcher.register_task_handler("system.service", ServiceManageTask)
    dispatcher.register_provider("system.service", ServiceInfoProvider)