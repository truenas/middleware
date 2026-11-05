import os
import sys

import pytest

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import extended_tests, ha
except ImportError:
    extended_tests = False
    ha = False

__all__ = ["extended_test", "fail", "ha_test", "non_ha_test"]

failed = [None]

ha_test = pytest.mark.skipif(not ha, reason="Test is only valid for HA")
non_ha_test = pytest.mark.skipif(ha, reason="Test is not valid for HA")
extended_test = pytest.mark.skipif(not extended_tests, reason="Test only runs with --extended_tests")


def fail(reason):
    """
    Prematurely abort the whole test suite execution, failing the test where this function is called
    (as opposed to just using `pytest.exit` which will not fail the test, and, if no previous tests failed, junit
    Jenkins plugin will display the test suite as green)
    """
    failed[0] = reason
    assert False, reason
