import time

class Train(object):
    _name = None
    _descr = None
    _seqno = None
    _time = None
    _notes = None
    _notice = None
    _update = False

    def __init__(self, name, description = None, sequence = None, checked = None):
        self._name = name
        self._descr = description
        self._seqno = sequence
        self._time = checked
        return

    def __repr__(self):
        retval = "Train('%s'" % self._name
        if self._descr: retval += ", '%s'" % self._descr
        if self._seqno: retval += ", '%s'" % self._seqno
        if self._time: retval += ", '%s'" % self._time
        retval += ")"
        return retval

    def Name(self):
        return self._name

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

    def SetLastCheckedTime(self, time = str(int(time.time()))):
        self._time = time
        return

    def Notice(self):
        return self._notice

    def SetNotice(self, notice):
        self._notice = notice

    def Notes(self):
        return self._notes

    def SetNotes(self, notes):
        self._notes = notes

    def SetUpdate(self, u):
        self._update = u

    def UpdateAvailable(self):
        return self._update

