import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from auto_config import dev_test
from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_01_non_silent_service_start_failure():
    """
    This test is strategically put here so that we test
    middleware's api for catching error message(s) related
    to when a service doesn't cleanly start/stop. We chose
    the UPS service, because it doesn't start without a
    proper config. We don't really care if it's start/stop,
    we just need to make sure that middleware raises a CallError.
    """
    with pytest.raises(CallError):
        call("service.start", "ups", {"silent": False})
