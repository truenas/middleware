

from . import (_module_dir, _module_name)
from . import TestStatus


class __handler(TestStatus):
    """
    Default handler for tests, when a real one isn't
    specified.  This only prints to stdout, and will never
    set (or remove) an alert.
    """

    def __init__(self, verbose=False, alert=False):
        super(self.__class__, self).__init__(verbose, alert)
        self._alert = False


class TestObject(object):
    def __init__(self, handler=None):
        if handler is None:
            self._handler = __handler(verbose=True)
        else:
            self._handler = handler

    def Enabled(self):
        return True

    def Test(self):
        return True

    def Requires(self):
        return []
