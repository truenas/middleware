__author__ = 'jceel'

from select import kqueue, kevent

class ProcessWatcher(object):
    def __init__(self, callback = None):
        self.__pids = []
        self.__callback = callback


    def start(self):
        pass


    def stop(self):
        pass

