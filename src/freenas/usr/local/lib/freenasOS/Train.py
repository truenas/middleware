import os
import sys

import Exceptions

class Train(object):
    _name = None
    _descr = None
    _seqno = None
    _time = None

    def __init__(name, description = None):
        self._name = name
        self._descr = description
        return

    def Description(self):
        return self._descr

    def SetDescription(self, description):
        self._descr = description
        return

    def LastSequence(self):
        return self._seqno

    def SetLastSequence(self, seqnum):
        self._seqno = seqnum
        return

    def LastCheckedTime(self):
        return self._time

    def SetLastCheckedTime(self, time):
        self._time = time
        return
