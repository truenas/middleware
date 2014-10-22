__author__ = 'jceel'

import struct
from gevent.subprocess import check_output
from task import Provider
from lib.freebsd import read_sysctl

class SystemInfoProvider(Provider):
    def uname_full(self):
        return check_output(["/usr/bin/uname", "-a"])

    def memory_size(self):
        return struct.unpack('Q', read_sysctl("hw.realmem"))

    def cpu_model(self):
        return read_sysctl("hw.model")


def _init(dispatcher):
    dispatcher.register_provider("system.info", SystemInfoProvider)