__author__ = 'jceel'

import gevent
import time
import logging
from gevent.queue import Queue
from gevent.event import Event
from task import TaskException, TaskStatus


class QueueClass(object):
    SYSTEM = 'SYSTEM'
    DISK = 'DISK'


class TaskState(object):
    CREATED = 'CREATED'
    WAITING = 'WAITING'
    EXECUTING = 'EXECUTING'
    FINISHED = 'FINISHED'
    FAILED = 'FAILED'
    ABORTED = 'ABORTED'


class WorkerState(object):
    IDLE = 'IDLE'
    EXECUTING = 'EXECUTING'
    WAITING = 'WAITING'


class Task(object):
    def __init__(self, dispatcher, name=None):
        self.dispatcher = dispatcher
        self.created_at = None
        self.started_at = None
        self.finished_at = None
        self.id = None
        self.name = name
        self.clazz = None
        self.args = None
        self.user = None
        self.state = TaskState.CREATED
        self.progress = None
        self.queues = []
        self.thread = None
        self.instance = None
        self.ended = Event()

    def __getstate__(self):
        return {
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "name": self.name,
            "args": self.args,
            "state": self.state
        }

    def __emit_progress(self):
        self.dispatcher.dispatch_event("task.progress", {
            "id": self.id,
            "percentage": self.progress.percentage,
            "message": self.progress.message,
            "extra": self.progress.extra
        })

    def run(self):
        gevent.spawn(self.progress_watcher)
        return self.instance.run(*self.args)

    def set_state(self, state, progress=None):
        if state == TaskState.EXECUTING:
            self.started_at = time.time()

        if state == TaskState.FINISHED:
            self.finished_at = time.time()

        self.state = state
        self.dispatcher.dispatch_event("task.updated", {"id": self.id, "state": state})
        self.dispatcher.datastore.update('tasks', self.id, self)

        if progress:
            self.progress = progress
            self.__emit_progress()

    def progress_watcher(self):
        while True:
            if self.ended.wait(1):
                return
            progress = self.instance.get_status()
            self.progress = progress
            self.__emit_progress()


class TaskQueue(Queue):
    def __init__(self, name, clazz):
        self.name = name
        self.clazz = clazz
        self.worker = None
        super(TaskQueue, self).__init__()

    def create_worker(self):
        self.worker = Worker(self)
        return gevent.spawn(self.worker.run)


class Balancer(object):
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self.task_list = []
        self.task_queue = Queue()
        self.queues = {}
        self.threads = []
        self.logger = logging.getLogger('Balancer')
        self.dispatcher.require_collection('tasks', 'serial', 'log')
        self.create_initial_queues()

    def create_initial_queues(self):
        self.create_queue(QueueClass.SYSTEM, 'system')

    def create_queue(self, queue_class, name):
        self.queues[name] = TaskQueue(name, queue_class)
        self.threads.append(self.queues[name].create_worker())
        self.logger.info("Created queue %s (class: %s)", name, queue_class)

    def start(self):
        self.threads.append(gevent.spawn(self.distribution_thread))
        self.logger.info("Started")

    def submit(self, name, args):
        if name not in self.dispatcher.tasks:
            self.logger.warning("Cannot submit task: unknown task type %s", name)
            return None

        task = Task(self.dispatcher, name)
        task.created_at = time.time()
        task.clazz = self.dispatcher.tasks[name]
        task.args = args
        task.state = TaskState.CREATED
        task.id = self.dispatcher.datastore.insert("tasks", task)
        self.task_list.append(task)
        self.task_queue.put(task)
        self.dispatcher.dispatch_event('task.created', {'id': task.id, 'type': name, 'state': task.state})
        self.logger.info("Task %d submitted (type: %s, class: %s)", task.id, name, task.clazz)
        return task.id

    def abort(self, id):
        task = self.get_task(id)
        if not task:
            self.logger.warning("Cannot abort task: unknown task id %d", id)
            return

        success = False
        try:
            success = task.instance.abort()
        except:
            pass

        if success:
            task.ended.set()
            task.set_state(TaskState.ABORTED, TaskStatus(0, "Aborted"))

    def distribution_thread(self):
        while True:
            task = self.task_queue.get()

            try:
                self.logger.debug("Picked up task %d: %s with args %s", task.id, task.name, task.args)
                task.instance = task.clazz(self.dispatcher)
                task.queues = task.instance.verify(*task.args)
            except Exception as err:
                self.logger.warning("Cannot verify task %d: %s", task.id, err)
                task.set_state(TaskState.FAILED, TaskStatus(0, str(err)))
                continue

            for i in task.queues:
                self.queues[i].put(task)

            task.set_state(TaskState.WAITING)
            self.logger.debug("Task %d assigned to queues %s", task.id, task.queues)


    def get_active_tasks(self):
        return filter(lambda x: x.state in (
            TaskState.CREATED,
            TaskState.WAITING,
            TaskState.EXECUTING),
            self.task_list)

    def get_tasks(self, type=None):
        if type is None:
            return self.task_list

        return filter(lambda x: x.state == type, self.task_list)

    def get_task(self, id):
        ret = filter(lambda x: x.id == id, self.task_list)
        if len(ret) > 0:
            return ret[0]


class Worker(object):
    def __init__(self, queue):
        self.queue = queue
        self.state = WorkerState.IDLE
        self.logger = logging.getLogger("Worker:{}".format(self.queue.name))

    def run(self):
        self.logger.info("Started")
        while True:
            self.state = WorkerState.WAITING
            task = self.queue.get()
            if task.state == TaskState.EXECUTING:
                task.ended.wait()
                continue

            self.state = WorkerState.EXECUTING
            task.set_state(TaskState.EXECUTING)
            try:
                result = task.run()
            except BaseException, e:
                task.ended.set()
                task.set_state(TaskState.FAILED, TaskStatus(0, str(e)))
                continue

            status = TaskStatus(100, '') if result == TaskState.FINISHED else None

            task.ended.set()
            task.set_state(result, status)