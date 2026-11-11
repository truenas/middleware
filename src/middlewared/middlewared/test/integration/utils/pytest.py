import os
import sys

import pytest

try:
    apifolder = os.getcwd()
    sys.path.append(apifolder)
    from auto_config import enterprise_tests, extended_tests, ha
except ImportError:
    enterprise_tests = False
    extended_tests = False
    ha = False

__all__ = ["enterprise_test", "extended_test", "fail", "ha_test", "non_enterprise_test", "non_ha_test"]

failed = [None]

ha_test = pytest.mark.skipif(not ha, reason="Test is only valid for HA")
non_ha_test = pytest.mark.skipif(ha, reason="Test is not valid for HA")
enterprise_test = pytest.mark.skipif(
    not (enterprise_tests or ha), reason="Test only runs with --enterprise_tests or HA"
)
non_enterprise_test = pytest.mark.skipif(
    enterprise_tests or ha, reason="Test only runs without --enterprise_tests and HA"
)
extended_test = pytest.mark.skipif(not extended_tests, reason="Test only runs with --extended_tests")


def fail(reason):
    """
    Prematurely abort the whole test suite execution, failing the test where this function is called
    (as opposed to just using `pytest.exit` which will not fail the test, and, if no previous tests failed, junit
    Jenkins plugin will display the test suite as green)
    """
    failed[0] = reason
    assert False, reason
