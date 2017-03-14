

import os
import sys

_module_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tests")
_module_name = os.path.basename(os.path.dirname(__file__))

ALERT_FILE = "/tmp/self-test-alert"

TEST_PASS = "PASS"
TEST_WARNING = "WARN"
TEST_FAIL = "FAIL"
TEST_CRITICAL = "CRIT"

from .TestStatus import TestStatus


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


def __LoadModule(path, name="module"):
        """
        Load the source file at path, calling it <name>.
        """
        try:
            if sys.version_info[0] < 3:
                import imp
                return imp.load_source(name, path)
            elif sys.version_info[1] < 5:
                from importlib.machinery import SourceFileLoader
                return SourceFileLoader(name, path).load_module()
            else:
                import importlib.util
                spec = importlib.util.spec_from_file_location(name, path)
                rv = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(rv)
                return rv
        except:
                return None


# Should this be a bunch of functions, or a class with
# methods?

def Tests():
    for fname in os.listdir(_module_dir):
        p = os.path.join(_module_dir, fname)
        if not os.path.isfile(p):
            continue
        if not p.endswith(".py"):
            continue
        if fname == "__init__.py":
            continue
        # Name of the module excluding .py
        yield fname[:-3]


def RunTest(name, handler):
    """
    Run a single test.
    """

    test_path = os.path.join(_module_dir, name + ".py")
    try:
        x = __LoadModule(test_path, name)
        for test in x.List():
            test_object = eval("x.%s(handler)" % test)
            if test_object.Enabled() and not test_object.Test():
                # Test failed, stop
                return False
    except BaseException as e:
            print("Couldn't load test %s: %s" % (name, str(e)))

    return True
