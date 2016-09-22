from collections import OrderedDict
from datetime import datetime

import enum


class State(enum.Enum):
    RUNNING = 1
    SUCCESS = 2
    FAILED = 3


class JobsDeque(object):
    """
    A jobs deque to do not keep more than `maxlen` in memory
    with a `id` assigner.
    """

    def __init__(self, maxlen=1000):
        self.maxlen = 1000
        self.count = 0
        self.__dict = OrderedDict()

    def add(self, job):
        self.count += 1
        job.set_id(self.count)
        if len(self.__dict) > self.maxlen:
            self.__dict.popitem(last=False)
        self.__dict[job.id] = job

    def all(self):
        return self.__dict


class Job(object):
    """
    Represents a long running call, methods marked with @job decorator
    """

    def __init__(self):
        self.id = None
        self.result = None
        self.state = State.RUNNING
        self.progress = {
            'percent': None,
            'description': None,
        }
        self.time_started = datetime.now()
        self.time_finished = None

    def set_id(self, id):
        self.id = id

    def set_result(self, result):
        self.result = result

    def set_state(self, state):
        assert self.state == State.RUNNING and state != 'RUNNING'
        self.state = State.__members__[state]
        self.time_finished = datetime.now()

    def set_progress(self, percent, description=None):
        if percent is not None:
            assert isinstance(percent, int)
            self.progress['percent'] = percent
        if description:
            self.progress['description'] = description

    def __encode__(self):
        return {
            'id': self.id,
            'progress': self.progress,
            'result': self.result,
            'state': self.state.name,
            'time_started': self.time_started,
            'time_finished': self.time_finished,
        }
