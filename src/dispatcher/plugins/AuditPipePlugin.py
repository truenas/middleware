__author__ = 'jceel'

import fcntl
from event import EventSource

class AuditPipeEventSource(EventSource):
    def __init__(self, dispatcher):
        super(AuditPipeEventSource, self).__init__(dispatcher);
        self.register_event_type("system.process.start")
        self.register_event_type("system.process.exit")


    def run(self):
        self.fd = open("/dev/auditpipe")

        while True:
            line = f.readline()
            if line is None:
                # Connection closed - we need to reconnect
                pass

def _init(dispatcher):
    pass