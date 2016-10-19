from middlewared.schema import accepts
from middlewared.service import Service

import sys

if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')

from freenasOS import Configuration


class SystemService(Service):

    def __init__(self, *args, **kwargs):
        super(SystemService, self).__init__(*args, **kwargs)
        self.__version = None

    @accepts()
    def is_freenas(self):
        """
        Returns `true` if running system is a FreeNAS or `false` is Something Else.
        """
        # This is a stub calling notifier until we have all infrastructure
        # to implement in middlewared
        return self.middleware.call('notifier.is_freenas')

    @accepts()
    def version(self):
        if self.__version is None:
            conf = Configuration.Configuration()
            sys_mani = conf.SystemManifest()
            if sys_mani:
                self.__version = sys_mani.Version()
        return self.__version
