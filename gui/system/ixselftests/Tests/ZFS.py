

import libzfs

from system.ixselftests import TestObject


def List():
    return ["ZFS"]


class ZFS(TestObject):
    def __init__(self, handler=None):
        super(self.__class__, self).__init__(handler)

    def Enabled(self):
        return True

    def Test(self):
        rv = True
        zfs = libzfs.ZFS()
        for pool in zfs.pools:
            if pool.status != "ONLINE":
                self._handler.Fail(test="Pool %s" % pool.name, status=pool.status)
                rv = False
            else:
                self._handler.Pass(test="Pool %s" % pool.name)
        return rv
