__author__ = 'jceel'

import errno
from gevent.event import Event
from lib import zfs
from lib.system import system, SubprocessException
from task import Provider, Task, TaskStatus, TaskException
from balancer import TaskState

class ZpoolProvider(Provider):
    def list_pools(self):
        return zfs.list_pools()

    def pool_status(self, pool):
        return str(zfs.zpool_status(pool))


class ZfsProvider(Provider):
    def list_datasets(self, pool):
        zfs.list_datasets(pool, recursive=True, include_root=True)

    def list_snapshots(self, pool):
        return []


class ZpoolScrubTask(Task):
    def __init__(self, dispatcher):
        self.pool = None
        self.dispatcher = dispatcher
        self.started = False
        self.finish_event = Event()

    def __scrub_finished(self, args):
        self.state = TaskState.FINISHED
        if args["pool"] == self.pool:
            self.finish_event.set()

    def run(self, pool):
        self.pool = pool
        self.dispatcher.register_event_handler("fs.zfs.scrub.finish", self.__scrub_finished)
        self.finish_event.clear()
        try:
            system(["/sbin/zpool", "scrub", self.pool])
            self.started = True
        except SubprocessException, e:
            raise TaskException(errno.EINVAL, e.err)

        self.finish_event.wait()
        return self.state

    def abort(self):
        try:
            system(["/sbin/zpool", "scrub", "-s", self.pool])
        except SubprocessException, e:
            raise TaskException(errno.EINVAL, e.err)

        return True

    def get_status(self):
        if not self.started:
            return TaskStatus(0, "Waiting to start...")

        scrub = zfs.zpool_status(self.pool).scrub
        if scrub["status"] == "IN_PROGRESS":
            self.progress = float(scrub["progress"])
            return TaskStatus(self.progress, "In progress...")

        if scrub["status"] == "CANCELED":
            self.state = TaskState.ABORTED
            self.finish_event.set()
            return TaskStatus(self.progress, "Canceled")

        if scrub["status"] == "CANCELED":
            self.finish_event.set()
            return TaskStatus(100, "Finished")


    def verify(self, pool):
        pool = zfs.zpool_status(pool)
        return pool.get_disks()





def _init(dispatcher):
    dispatcher.register_provider("zfs.pool", ZpoolProvider)
    dispatcher.register_task_handler("zfs.pool.scrub", ZpoolScrubTask)