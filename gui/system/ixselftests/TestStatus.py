

import os

from . import ALERT_FILE
from . import (_module_dir, _module_name)


class TestStatus(object):
    def __init__(self, verbose=False, alert=False):
        self._verbose = verbose
        self._alert = alert
        if self._alert:
            try:
                os.path.remove(ALERT_FILE)
            except:
                pass

    def Pass(self, test=None, module=None, message=None):
        st = "[PASS]"
        if self._verbose and test:
            st = st + " " + test
        if self._verbose and module:
            st = st + " " + module
        if message:
            st = st + " " + message
        if self._verbose:
            print(st)

        if self._verbose and self._alert:
            with open(ALERT_FILE, "a") as f:
                f.write(st + "\n")
        return True

    def Fail(self, test=None, module=None, message=None, severity=None):
        if severity is None:
            st = "[FAIL]"
        else:
            st = "[%s]" % severity
        if test:
            st = st + " " + test
        if module:
            st = st + " " + module
        if message:
            st = st + " " + message

        if self._verbose:
            print(st)

        if self._alert:
            with open(ALERT_FILE, "a") as f:
                f.write(st + "\n")
        return False
