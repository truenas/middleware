__author__ = 'jceel'

import errno
from gevent import Timeout
from watchdog import events
from task import Task, TaskStatus, Provider, TaskException
from balancer import TaskState
from event import EventSource
from lib.system import system, SubprocessException

class ServiceStatusEventSource(EventSource):
    def __init__(self, dispatcher):
        super(ServiceStatusEventSource, self).__init__(dispatcher)
        self.register_event_type("system.service.started")
        self.register_event_type("system.service.stopped")

    def __on_process_exit(self):
        pass

    def run(self):
        pass

class ServiceInfoProvider(Provider):
    def list_services(self):
        try:
            out, err = system(["/usr/sbin/service", "-l"])
        except SubprocessException, e:
            raise TaskException(errno.ENXIO, e.err)

    def get_service_info(self, service):
        pass

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
    dispatcher.register_event_source("system.service", ServiceStatusEventSource)
    dispatcher.register_task_handler("system.service", ServiceManageTask)
    dispatcher.register_provider("system.service", ServiceInfoProvider)