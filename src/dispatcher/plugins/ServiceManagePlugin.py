__author__ = 'jceel'

import errno
from gevent import Timeout
from watchdog import events
from task import Task, TaskStatus, Provider, TaskException, description, schema
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